from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|paid|failed|refunded
    order_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|confirmed|shipped|delivered|cancelled
    shipping_address_id: Mapped[int | None] = mapped_column(ForeignKey("user_addresses.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_order_user_idempotency"),)


class OrderItem(Base):
    """Snapshots keep order history stable when products/prices change later.
    seller_id enables per-seller fulfilment of multi-seller orders."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    seller_listing_id: Mapped[int] = mapped_column(ForeignKey("seller_listings.id"))
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(320))
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int]
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fulfillment_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|shipped|delivered

    order: Mapped[Order] = relationship(back_populates="items")
