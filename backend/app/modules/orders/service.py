import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.modules.cart.models import Cart
from app.modules.inventory import service as inventory
from app.modules.orders.models import Order, OrderItem
from app.modules.payments.models import Payment
from app.modules.products.models import Product, ProductVariant, SellerListing
from app.modules.sellers.models import Seller
from app.modules.users.models import User, UserAddress

log = logging.getLogger(__name__)

# Valid order_status transitions. Anything else is rejected.
ORDER_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def _transition(order: Order, new_status: str) -> None:
    if new_status not in ORDER_TRANSITIONS[order.order_status]:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot move order from {order.order_status} to {new_status}")
    order.order_status = new_status


def _order_query():
    return select(Order).options(selectinload(Order.items))


def get_order_for_user(db: Session, order_id: int, user: User) -> Order:
    order = db.scalar(_order_query().where(Order.id == order_id))
    if order is None or (order.user_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


def create_order(db: Session, user: User, shipping_address_id: int, idempotency_key: str | None) -> Order:
    if idempotency_key:
        existing = db.scalar(_order_query().where(Order.user_id == user.id, Order.idempotency_key == idempotency_key))
        if existing:
            return existing

    address = db.get(UserAddress, shipping_address_id)
    if address is None or address.user_id != user.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid shipping address")

    cart = db.scalar(select(Cart).where(Cart.user_id == user.id).options(selectinload(Cart.items)))
    if cart is None or not cart.items:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cart is empty")

    listing_ids = [i.seller_listing_id for i in cart.items]
    rows = {
        listing.id: (listing, variant, product, seller)
        for listing, variant, product, seller in db.execute(
            select(SellerListing, ProductVariant, Product, Seller)
            .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .join(Seller, Seller.id == SellerListing.seller_id)
            .where(SellerListing.id.in_(listing_ids))
        )
    }
    locked = inventory.lock_inventory(db, listing_ids)

    order = Order(
        user_id=user.id,
        order_number=f"ORD-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}",
        total_amount=Decimal("0"),
        shipping_address_id=address.id,
        idempotency_key=idempotency_key,
    )
    total = Decimal("0")
    for item in cart.items:
        row = rows.get(item.seller_listing_id)
        if row is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "An item in your cart is no longer available")
        listing, variant, product, seller = row
        label = f"{product.name} ({variant.variant_name})"
        if listing.status != "active" or product.status != "active" or seller.approval_status != "approved":
            raise HTTPException(status.HTTP_409_CONFLICT, f"{label} is no longer available")
        inv = locked.get(listing.id)
        if inv is None:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{label} is out of stock")
        inventory.reserve(inv, item.quantity, label)
        subtotal = listing.selling_price * item.quantity  # price is read from the DB, never from the client
        total += subtotal
        order.items.append(
            OrderItem(
                seller_listing_id=listing.id,
                seller_id=seller.id,
                product_name_snapshot=f"{product.name} — {variant.variant_name}"[:320],
                price_snapshot=listing.selling_price,
                quantity=item.quantity,
                subtotal=subtotal,
            )
        )
    order.total_amount = total
    db.add(order)
    for item in list(cart.items):
        db.delete(item)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent duplicate request with the same idempotency key.
        db.rollback()
        existing = db.scalar(_order_query().where(Order.user_id == user.id, Order.idempotency_key == idempotency_key))
        if existing:
            return existing
        raise
    return db.scalar(_order_query().where(Order.id == order.id))


def _release_reservations(db: Session, order: Order) -> None:
    locked = inventory.lock_inventory(db, [i.seller_listing_id for i in order.items])
    for item in order.items:
        if item.seller_listing_id in locked:
            inventory.release(locked[item.seller_listing_id], item.quantity)


def cancel_order(db: Session, order: Order) -> Order:
    if order.order_status not in ("pending", "confirmed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {order.order_status} order cannot be cancelled")
    if any(i.fulfillment_status != "pending" for i in order.items):
        raise HTTPException(status.HTTP_409_CONFLICT, "Part of this order has already shipped")
    was_paid = order.payment_status == "paid"
    _transition(order, "cancelled")
    if was_paid:
        # Not yet shipped: put units back on hand and mark the payment refunded.
        locked = inventory.lock_inventory(db, [i.seller_listing_id for i in order.items])
        for item in order.items:
            if item.seller_listing_id in locked:
                inventory.restock(locked[item.seller_listing_id], item.quantity)
        order.payment_status = "refunded"
        for p in db.scalars(select(Payment).where(Payment.order_id == order.id, Payment.status == "succeeded")):
            p.status = "refunded"
    else:
        _release_reservations(db, order)
        order.payment_status = "failed"
        for p in db.scalars(select(Payment).where(Payment.order_id == order.id, Payment.status == "pending")):
            p.status = "failed"
    db.commit()
    return order


def confirm_paid(db: Session, order: Order) -> None:
    """Payment verified server-side: convert reservations into a real stock deduction."""
    locked = inventory.lock_inventory(db, [i.seller_listing_id for i in order.items])
    for item in order.items:
        inv = locked.get(item.seller_listing_id)
        if inv is not None:
            inventory.commit_sale(inv, item.quantity)
    order.payment_status = "paid"
    _transition(order, "confirmed")


def expire_pending_orders(db: Session) -> int:
    """Cancels unpaid orders whose reservation window elapsed, releasing the held stock."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.order_reservation_minutes)
    stale = db.scalars(
        _order_query().where(Order.order_status == "pending", Order.created_at < cutoff).with_for_update(of=Order)
    ).all()
    for order in stale:
        cancel_order(db, order)
    return len(stale)


def update_fulfilment(db: Session, seller: Seller, order_id: int, target: str) -> Order:
    order = db.scalar(_order_query().where(Order.id == order_id).with_for_update(of=Order))
    mine = [i for i in order.items if i.seller_id == seller.id] if order else []
    if not mine:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.order_status not in ("confirmed", "shipped"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Order is {order.order_status}; it cannot be fulfilled")
    required = "pending" if target == "shipped" else "shipped"
    for item in mine:
        if item.fulfillment_status != required:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Items must be {required} before marking {target}")
        item.fulfillment_status = target

    states = {i.fulfillment_status for i in order.items}
    if states == {"delivered"}:
        derived = "delivered"
    elif states <= {"shipped", "delivered"}:
        derived = "shipped"
    else:
        derived = "confirmed"
    if derived != order.order_status:
        _transition(order, derived)
    db.commit()
    return order
