from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Inventory(Base):
    """available_quantity = units on hand; reserved_quantity = held by pending orders.
    Sellable stock = available_quantity - reserved_quantity."""

    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_listing_id: Mapped[int] = mapped_column(ForeignKey("seller_listings.id", ondelete="CASCADE"), unique=True)
    available_quantity: Mapped[int] = mapped_column(default=0)
    reserved_quantity: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("available_quantity >= 0", name="ck_inventory_available_nonneg"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonneg"),
        CheckConstraint("reserved_quantity <= available_quantity", name="ck_inventory_reserved_lte_available"),
    )
