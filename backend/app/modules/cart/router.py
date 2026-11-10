from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.cart.models import Cart, CartItem
from app.modules.inventory.models import Inventory
from app.modules.products.models import Product, ProductImage, ProductVariant, SellerListing
from app.modules.sellers.models import Seller
from app.modules.users.models import User

router = APIRouter(prefix="/cart", tags=["cart"])


class CartItemIn(BaseModel):
    seller_listing_id: int
    quantity: int = Field(ge=1, le=100)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=100)


class CartItemOut(BaseModel):
    id: int
    seller_listing_id: int
    product_id: int
    product_name: str
    variant_name: str
    seller_name: str
    image_url: str | None
    unit_price: Decimal
    quantity: int
    available_quantity: int
    subtotal: Decimal


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal


def _get_or_create_cart(db: Session, user: User) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()
    return cart


def _render(db: Session, cart: Cart) -> CartOut:
    rows = db.execute(
        select(CartItem, SellerListing, ProductVariant, Product, Seller.store_name, Inventory)
        .join(SellerListing, SellerListing.id == CartItem.seller_listing_id)
        .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .join(Seller, Seller.id == SellerListing.seller_id)
        .join(Inventory, Inventory.seller_listing_id == SellerListing.id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.id)
    ).all()
    images: dict[int, str] = {}
    if rows:
        for pid, url in db.execute(
            select(ProductImage.product_id, ProductImage.image_url)
            .where(ProductImage.product_id.in_({r[3].id for r in rows}))
            .order_by(ProductImage.is_primary.asc(), ProductImage.id.desc())
        ):
            images[pid] = url
    items, total = [], Decimal("0")
    for item, listing, variant, product, store_name, inv in rows:
        subtotal = listing.selling_price * item.quantity
        total += subtotal
        items.append(
            CartItemOut(
                id=item.id,
                seller_listing_id=listing.id,
                product_id=product.id,
                product_name=product.name,
                variant_name=variant.variant_name,
                seller_name=store_name,
                image_url=images.get(product.id),
                unit_price=listing.selling_price,
                quantity=item.quantity,
                available_quantity=max(inv.available_quantity - inv.reserved_quantity, 0),
                subtotal=subtotal,
            )
        )
    return CartOut(items=items, total=total)


def _sellable(db: Session, listing_id: int) -> int:
    inv = db.scalar(select(Inventory).where(Inventory.seller_listing_id == listing_id))
    return max(inv.available_quantity - inv.reserved_quantity, 0) if inv else 0


@router.get("", response_model=CartOut)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart = _get_or_create_cart(db, user)
    db.commit()
    return _render(db, cart)


@router.post("/items", response_model=CartOut)
def add_item(body: CartItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(
        select(SellerListing, Product, Seller)
        .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .join(Seller, Seller.id == SellerListing.seller_id)
        .where(SellerListing.id == body.seller_listing_id)
    ).first()
    if row is None or row[0].status != "active" or row[1].status != "active" or row[2].approval_status != "approved":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not available")
    if row[2].user_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot buy your own listing")

    cart = _get_or_create_cart(db, user)
    existing = db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.seller_listing_id == body.seller_listing_id))
    new_qty = (existing.quantity if existing else 0) + body.quantity
    if new_qty > _sellable(db, body.seller_listing_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Not enough stock available")
    if existing:
        existing.quantity = new_qty
    else:
        db.add(CartItem(cart_id=cart.id, seller_listing_id=body.seller_listing_id, quantity=new_qty))
    db.commit()
    return _render(db, cart)


def _own_item(db: Session, user: User, item_id: int) -> tuple[Cart, CartItem]:
    cart = _get_or_create_cart(db, user)
    item = db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart item not found")
    return cart, item


@router.put("/items/{item_id}", response_model=CartOut)
def update_item(item_id: int, body: CartItemUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart, item = _own_item(db, user, item_id)
    if body.quantity > _sellable(db, item.seller_listing_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Not enough stock available")
    item.quantity = body.quantity
    db.commit()
    return _render(db, cart)


@router.delete("/items/{item_id}", response_model=CartOut)
def delete_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart, item = _own_item(db, user, item_id)
    db.delete(item)
    db.commit()
    return _render(db, cart)
