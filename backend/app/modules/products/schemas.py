from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCard(BaseModel):
    id: int
    name: str
    brand: str | None = None
    description: str
    category_id: int
    category_name: str
    primary_image_url: str | None = None
    min_price: Decimal | None = None
    in_stock: bool = False
    avg_rating: float | None = None
    review_count: int = 0


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    is_primary: bool


class ListingView(BaseModel):
    id: int
    seller_id: int
    seller_name: str
    selling_price: Decimal
    available_quantity: int


class VariantView(BaseModel):
    id: int
    sku: str
    variant_name: str
    attributes: dict
    listings: list[ListingView]


class ProductDetail(ProductCard):
    specifications: dict
    status: str
    seller_id: int
    images: list[ImageOut]
    variants: list[VariantView]


class ProductList(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProductCard]


class VariantInput(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    variant_name: str = Field(min_length=1, max_length=160)
    attributes: dict = Field(default_factory=dict)
    selling_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    quantity: int = Field(ge=0, le=1_000_000)


class ProductInput(BaseModel):
    category_id: int
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(max_length=10_000)
    brand: str | None = Field(default=None, max_length=120)
    specifications: dict = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list, max_length=10)
    variants: list[VariantInput] = Field(min_length=1, max_length=50)

    @field_validator("image_urls")
    @classmethod
    def _safe_image_urls(cls, urls: list[str]) -> list[str]:
        # Uploaded images (our media path) or plain http(s) links; nothing like javascript: or data: URIs.
        for url in urls:
            if len(url) > 1000 or not url.startswith(("/api/v1/media/", "https://", "http://")):
                raise ValueError("image_urls must be uploaded images or http(s) URLs")
        return urls


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    brand: str | None = Field(default=None, max_length=120)
    category_id: int | None = None
    specifications: dict | None = None
    status: Literal["active", "draft", "archived"] | None = None


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str | None = Field(default=None, max_length=4000)


class ReviewOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    product_id: int
    rating: int
    review_text: str | None
    created_at: datetime
