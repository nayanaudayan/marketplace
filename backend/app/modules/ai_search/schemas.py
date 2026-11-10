from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.products.schemas import ProductCard, ProductDetail


class SearchFilters(BaseModel):
    category: str | None = Field(default=None, max_length=60)
    brand: str | None = Field(default=None, max_length=60)
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    minimum_ram_gb: float | None = Field(default=None, gt=0, le=4096)


class AISearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    filters: SearchFilters | None = None
    conversation_id: int | None = None
    sort_by: Literal["relevance", "price_asc", "price_desc"] = "relevance"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class AIProduct(ProductCard):
    listing_id: int
    price: Decimal
    stock: int
    seller_name: str
    score: float
    match_reason: str


class AISearchResponse(BaseModel):
    query: str
    conversation_id: int | None
    extracted_filters: dict
    total: int
    explanation: str
    products: list[AIProduct]


class CompareRequest(BaseModel):
    product_ids: list[int] = Field(min_length=2, max_length=5)


class CompareResponse(BaseModel):
    products: list[ProductDetail]
    summary: str


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationOut(BaseModel):
    id: int
    title: str | None
    created_at: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    message: str
    created_at: datetime
