from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.inventory import service as inventory
from app.modules.orders import service as orders
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import OrderOut
from app.modules.products import service as products_service
from app.modules.products.models import Product, SellerListing
from app.modules.products.schemas import ProductDetail
from app.modules.sellers.dependencies import get_approved_seller, get_seller
from app.modules.sellers.models import Seller
from app.modules.sellers.schemas import (
    ListingOut,
    ListingUpdateIn,
    OrderStatusIn,
    SellerOrderItemOut,
    SellerOut,
    SellerRegisterIn,
    SellerUpdateIn,
)
from app.modules.users.models import User

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.post("/register", response_model=SellerOut, status_code=201)
def register_seller(body: SellerRegisterIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins cannot become sellers")
    if db.scalar(select(Seller.id).where(Seller.user_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Seller profile already exists")
    seller = Seller(user_id=user.id, store_name=body.store_name.strip(), store_description=body.store_description)
    user.role = "seller"
    db.add(seller)
    db.commit()
    return seller


@router.get("/profile", response_model=SellerOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 404 (not 403) when there is no store yet, so clients can offer the "set up your store" step.
    seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seller profile not found")
    return seller


@router.put("/profile", response_model=SellerOut)
def update_profile(body: SellerUpdateIn, seller: Seller = Depends(get_seller), db: Session = Depends(get_db)):
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(seller, field, value)
    db.commit()
    return seller


@router.get("/products", response_model=list[ProductDetail])
def my_products(seller: Seller = Depends(get_seller), db: Session = Depends(get_db)):
    products = db.scalars(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.seller_id == seller.id, Product.status != "archived")
        .order_by(Product.created_at.desc())
    ).all()
    return products_service.build_details(db, products)


@router.put("/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int, body: ListingUpdateIn, seller: Seller = Depends(get_approved_seller), db: Session = Depends(get_db)
):
    listing = db.get(SellerListing, listing_id)
    if listing is None or listing.seller_id != seller.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    inv = inventory.lock_inventory(db, [listing.id]).get(listing.id)
    if body.selling_price is not None:
        listing.selling_price = body.selling_price
    if body.available_quantity is not None and inv is not None:
        # The API speaks in sellable units; on-hand = sellable + units already held by pending orders.
        inv.available_quantity = body.available_quantity + inv.reserved_quantity
    db.commit()
    return ListingOut(
        id=listing.id,
        selling_price=listing.selling_price,
        available_quantity=inventory.sellable(inv) if inv else 0,
    )


@router.get("/orders", response_model=list[SellerOrderItemOut])
def seller_orders(seller: Seller = Depends(get_seller), db: Session = Depends(get_db)):
    rows = db.execute(
        select(OrderItem, Order)
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.seller_id == seller.id, Order.order_status != "pending")  # unpaid orders aren't actionable
        .order_by(Order.created_at.desc(), OrderItem.id)
    ).all()
    return [
        SellerOrderItemOut(
            order_id=o.id,
            order_number=o.order_number,
            order_status=o.order_status,
            fulfillment_status=i.fulfillment_status,
            product_name=i.product_name_snapshot,
            quantity=i.quantity,
            subtotal=i.subtotal,
            created_at=o.created_at,
        )
        for i, o in rows
    ]


@router.put("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: int, body: OrderStatusIn, seller: Seller = Depends(get_seller), db: Session = Depends(get_db)
):
    return orders.update_fulfilment(db, seller, order_id, body.order_status)
