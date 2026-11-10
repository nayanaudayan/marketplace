from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderCreateIn(BaseModel):
    shipping_address_id: int
    idempotency_key: str | None = Field(default=None, max_length=80)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    seller_listing_id: int
    product_name_snapshot: str
    price_snapshot: Decimal
    quantity: int
    subtotal: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    total_amount: Decimal
    payment_status: str
    order_status: str
    shipping_address_id: int | None
    created_at: datetime
    items: list[OrderItemOut]
