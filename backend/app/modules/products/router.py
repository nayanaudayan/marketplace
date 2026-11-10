from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, literal_column, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_user
from app.modules.products import service
from app.modules.products.filters import ProductFilters, build_filter_clauses
from app.modules.products.models import FTS_EXPRESSION, Product, ProductVariant, SellerListing
from app.modules.products.schemas import (
    ProductDetail,
    ProductInput,
    ProductList,
    ProductUpdate,
    ReviewIn,
    ReviewOut,
)
from app.modules.reviews.models import Review
from app.modules.sellers.dependencies import get_approved_seller
from app.modules.sellers.models import Seller
from app.modules.users.models import User

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductList)
def list_products(
    q: str | None = Query(default=None, max_length=200),
    category_id: int | None = None,
    brand: str | None = Query(default=None, max_length=120),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    in_stock: bool = False,
    sort_by: Literal["relevance", "price_asc", "price_desc", "newest"] = "relevance",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    clauses = build_filter_clauses(
        db, ProductFilters(category_id=category_id, brand=brand, min_price=min_price, max_price=max_price, in_stock=in_stock)
    )
    rank = None
    if q and q.strip():
        tsquery = func.plainto_tsquery("english", q)
        tsvector = literal_column(FTS_EXPRESSION)
        like = f"%{q.strip()}%"
        clauses.append(tsvector.op("@@")(tsquery) | Product.name.ilike(like) | Product.brand.ilike(like))
        rank = func.ts_rank(tsvector, tsquery)

    lowest_price = (
        select(func.min(SellerListing.selling_price))
        .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
        .where(ProductVariant.product_id == Product.id, SellerListing.status == "active")
        .scalar_subquery()
    )
    if sort_by == "price_asc":
        order = [lowest_price.asc(), Product.id]
    elif sort_by == "price_desc":
        order = [lowest_price.desc(), Product.id]
    elif sort_by == "relevance" and rank is not None:
        order = [rank.desc(), Product.id]
    else:
        order = [Product.created_at.desc(), Product.id.desc()]

    total = db.scalar(select(func.count()).select_from(Product).where(*clauses)) or 0
    products = db.scalars(select(Product).where(*clauses).order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return ProductList(total=total, page=page, page_size=page_size, items=service.build_cards(db, products))


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    product = service.get_product_or_404(db, product_id)
    if product.status != "active":
        owner = db.scalar(select(Seller.user_id).where(Seller.id == product.seller_id))
        if user is None or (user.id != owner and user.role != "admin"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return service.build_details(db, [product])[0]


@router.post("", response_model=ProductDetail, status_code=201)
def create_product(body: ProductInput, seller: Seller = Depends(get_approved_seller), db: Session = Depends(get_db)):
    product = service.create_product(db, seller, body)
    return service.build_details(db, [service.get_product_or_404(db, product.id)])[0]


def _owned_product(db: Session, product_id: int, user: User) -> Product:
    product = service.get_product_or_404(db, product_id)
    if user.role != "admin":
        seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
        if seller is None or seller.id != product.seller_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your product")
    return product


@router.put("/{product_id}", response_model=ProductDetail)
def update_product(
    product_id: int, body: ProductUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    product = _owned_product(db, product_id, user)
    service.update_product(db, product, body)
    return service.build_details(db, [service.get_product_or_404(db, product_id)])[0]


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = _owned_product(db, product_id, user)
    product.status = "archived"
    db.commit()
    return Response(status_code=204)


@router.get("/{product_id}/reviews", response_model=list[ReviewOut])
def list_reviews(product_id: int, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Review, User.name).join(User, User.id == Review.user_id).where(Review.product_id == product_id).order_by(Review.created_at.desc())
    ).all()
    return [
        ReviewOut(
            id=r.id, user_id=r.user_id, user_name=name, product_id=r.product_id,
            rating=r.rating, review_text=r.review_text, created_at=r.created_at,
        )
        for r, name in rows
    ]


@router.post("/{product_id}/reviews", response_model=ReviewOut, status_code=201)
def create_review(product_id: int, body: ReviewIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = service.get_product_or_404(db, product_id)
    own_seller = db.scalar(select(Seller.id).where(Seller.user_id == user.id))
    if own_seller == product.seller_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sellers cannot review their own products")
    review = Review(user_id=user.id, product_id=product_id, rating=body.rating, review_text=body.review_text)
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already reviewed this product")
    return ReviewOut(
        id=review.id, user_id=user.id, user_name=user.name, product_id=product_id,
        rating=review.rating, review_text=review.review_text, created_at=review.created_at,
    )
