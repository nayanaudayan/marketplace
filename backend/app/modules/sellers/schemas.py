from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SellerRegisterIn(BaseModel):
    store_name: str = Field(min_length=2, max_length=160)
    store_description: str | None = Field(default=None, max_length=2000)


class SellerUpdateIn(BaseModel):
    store_name: str | None = Field(default=None, min_length=2, max_length=160)
    store_description: str | None = Field(default=None, max_length=2000)


class SellerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    store_name: str
    store_description: str | None = None
    approval_status: str
    commission_percentage: Decimal


class ListingUpdateIn(BaseModel):
    selling_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    available_quantity: int | None = Field(default=None, ge=0, le=1_000_000)


class ListingOut(BaseModel):
    id: int
    selling_price: Decimal
    available_quantity: int


class SellerOrderItemOut(BaseModel):
    order_id: int
    order_number: str
    order_status: str
    fulfillment_status: str
    product_name: str
    quantity: int
    subtotal: Decimal
    created_at: datetime


class OrderStatusIn(BaseModel):
    order_status: Literal["shipped", "delivered"]
