from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.categories.models import Category
from app.modules.inventory.models import Inventory
from app.modules.products.models import Product, ProductImage, ProductVariant, SellerListing
from app.modules.products.schemas import (
    ListingView,
    ProductCard,
    ProductDetail,
    ProductInput,
    ProductUpdate,
    VariantView,
)
from app.modules.reviews.models import Review
from app.modules.sellers.models import Seller
from app.workers.tasks import enqueue_product_indexing

SELLABLE = Inventory.available_quantity - Inventory.reserved_quantity


def build_cards(db: Session, products: Sequence[Product]) -> list[ProductCard]:
    """Batch-builds ProductCards (price, stock, rating) with a handful of queries instead of N+1."""
    if not products:
        return []
    ids = [p.id for p in products]

    categories = dict(db.execute(select(Category.id, Category.name).where(Category.id.in_({p.category_id for p in products}))).all())

    images: dict[int, str] = {}
    for pid, url in db.execute(
        select(ProductImage.product_id, ProductImage.image_url)
        .where(ProductImage.product_id.in_(ids))
        .order_by(ProductImage.is_primary.asc(), ProductImage.id.desc())  # later rows overwrite: primary/first wins
    ):
        images[pid] = url

    price_rows = db.execute(
        select(
            ProductVariant.product_id,
            func.min(SellerListing.selling_price).filter(SELLABLE > 0),
            func.min(SellerListing.selling_price),
            func.bool_or(SELLABLE > 0),
        )
        .select_from(SellerListing)
        .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
        .join(Inventory, Inventory.seller_listing_id == SellerListing.id)
        .join(Seller, Seller.id == SellerListing.seller_id)
        .where(ProductVariant.product_id.in_(ids), SellerListing.status == "active", Seller.approval_status == "approved")
        .group_by(ProductVariant.product_id)
    ).all()
    prices = {pid: (min_stock if min_stock is not None else min_all, bool(stock)) for pid, min_stock, min_all, stock in price_rows}

    ratings = {
        pid: (float(avg), cnt)
        for pid, avg, cnt in db.execute(
            select(Review.product_id, func.avg(Review.rating), func.count(Review.id))
            .where(Review.product_id.in_(ids))
            .group_by(Review.product_id)
        )
    }

    cards = []
    for p in products:
        price, in_stock = prices.get(p.id, (None, False))
        avg, cnt = ratings.get(p.id, (None, 0))
        cards.append(
            ProductCard(
                id=p.id,
                name=p.name,
                brand=p.brand,
                description=p.description,
                category_id=p.category_id,
                category_name=categories.get(p.category_id, ""),
                primary_image_url=images.get(p.id),
                min_price=price,
                in_stock=in_stock,
                avg_rating=round(avg, 2) if avg is not None else None,
                review_count=cnt,
            )
        )
    return cards


def build_details(db: Session, products: Sequence[Product]) -> list[ProductDetail]:
    if not products:
        return []
    cards = {c.id: c for c in build_cards(db, products)}
    ids = [p.id for p in products]
    variants = db.scalars(
        select(ProductVariant).where(ProductVariant.product_id.in_(ids)).order_by(ProductVariant.id)
    ).all()
    listing_rows = db.execute(
        select(SellerListing, Seller.store_name, SELLABLE)
        .join(Seller, Seller.id == SellerListing.seller_id)
        .join(Inventory, Inventory.seller_listing_id == SellerListing.id)
        .where(SellerListing.product_variant_id.in_([v.id for v in variants]), SellerListing.status == "active")
        .order_by(SellerListing.selling_price)
    ).all()
    listings_by_variant: dict[int, list[ListingView]] = {}
    for listing, store_name, sellable in listing_rows:
        listings_by_variant.setdefault(listing.product_variant_id, []).append(
            ListingView(
                id=listing.id,
                seller_id=listing.seller_id,
                seller_name=store_name,
                selling_price=listing.selling_price,
                available_quantity=max(sellable, 0),
            )
        )
    variants_by_product: dict[int, list[VariantView]] = {}
    for v in variants:
        variants_by_product.setdefault(v.product_id, []).append(
            VariantView(
                id=v.id,
                sku=v.sku,
                variant_name=v.variant_name,
                attributes=v.attributes or {},
                listings=listings_by_variant.get(v.id, []),
            )
        )
    images = {p.id: sorted(p.images, key=lambda i: (not i.is_primary, i.id)) for p in products}
    return [
        ProductDetail(
            **cards[p.id].model_dump(),
            specifications=p.specifications or {},
            status=p.status,
            seller_id=p.seller_id,
            images=images[p.id],
            variants=variants_by_product.get(p.id, []),
        )
        for p in products
    ]


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.scalar(select(Product).options(selectinload(Product.images)).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


def create_product(db: Session, seller: Seller, data: ProductInput) -> Product:
    if db.get(Category, data.category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")
    skus = [v.sku for v in data.variants]
    if len(set(skus)) != len(skus):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Duplicate SKU in request")

    product = Product(
        seller_id=seller.id,
        category_id=data.category_id,
        name=data.name.strip(),
        description=data.description,
        brand=data.brand,
        specifications=data.specifications,
    )
    product.images = [ProductImage(image_url=url, is_primary=(i == 0)) for i, url in enumerate(data.image_urls)]
    for v in data.variants:
        variant = ProductVariant(sku=v.sku, variant_name=v.variant_name, attributes=v.attributes)
        listing = SellerListing(seller_id=seller.id, selling_price=v.selling_price)
        variant.listings = [listing]
        product.variants.append(variant)
    db.add(product)
    try:
        db.flush()
        for variant in product.variants:
            for listing in variant.listings:
                qty = next(v.quantity for v in data.variants if v.sku == variant.sku)
                db.add(Inventory(seller_listing_id=listing.id, available_quantity=qty))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "SKU already exists")
    enqueue_product_indexing(product.id)
    return product


def update_product(db: Session, product: Product, data: ProductUpdate) -> Product:
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes and (changes["category_id"] is None or db.get(Category, changes["category_id"]) is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")
    for field, value in changes.items():
        if value is None and field not in ("brand",):
            continue
        setattr(product, field, value)
    db.commit()
    enqueue_product_indexing(product.id)
    return product
