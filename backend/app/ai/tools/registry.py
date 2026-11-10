"""Controlled, validated backend functions an LLM agent may call (spec 11.2).

Every tool: validates its arguments with Pydantic, only exposes public marketplace data, and reads facts from
the database. The LLM can *request* a tool by name; it can never run SQL or reach anything outside this registry.
"""
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.inventory.models import Inventory
from app.modules.products.models import Product, ProductVariant, SellerListing
from app.modules.products.service import build_cards, build_details
from app.modules.reviews.models import Review
from app.modules.sellers.models import Seller


class ProductIdArgs(BaseModel):
    product_id: int


class SellerArgs(BaseModel):
    seller_id: int


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class CompareArgs(BaseModel):
    product_ids: list[int] = Field(min_length=2, max_length=5)


def _active_product(db: Session, product_id: int) -> Product | None:
    product = db.scalar(select(Product).options(selectinload(Product.images)).where(Product.id == product_id))
    return product if product and product.status == "active" else None


def search_products(db: Session, args: SearchArgs) -> list[dict]:
    like = f"%{args.query}%"
    products = db.scalars(
        select(Product).where(Product.status == "active", Product.name.ilike(like) | Product.brand.ilike(like)).limit(args.limit)
    ).all()
    return [c.model_dump(mode="json") for c in build_cards(db, products)]


def get_product_details(db: Session, args: ProductIdArgs) -> dict | None:
    product = _active_product(db, args.product_id)
    return build_details(db, [product])[0].model_dump(mode="json") if product else None


def get_inventory(db: Session, args: ProductIdArgs) -> dict | None:
    if _active_product(db, args.product_id) is None:
        return None
    total = db.scalar(
        select(func.coalesce(func.sum(Inventory.available_quantity - Inventory.reserved_quantity), 0))
        .select_from(Inventory)
        .join(SellerListing, SellerListing.id == Inventory.seller_listing_id)
        .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
        .where(ProductVariant.product_id == args.product_id, SellerListing.status == "active")
    )
    return {"product_id": args.product_id, "units_available": max(int(total or 0), 0)}


def get_seller_details(db: Session, args: SellerArgs) -> dict | None:
    seller = db.get(Seller, args.seller_id)
    if seller is None or seller.approval_status != "approved":
        return None
    return {"seller_id": seller.id, "store_name": seller.store_name, "store_description": seller.store_description}


def get_product_reviews(db: Session, args: ProductIdArgs) -> dict | None:
    if _active_product(db, args.product_id) is None:
        return None
    avg, count = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == args.product_id)
    ).one()
    recent = db.scalars(
        select(Review.review_text).where(Review.product_id == args.product_id, Review.review_text.is_not(None)).order_by(Review.created_at.desc()).limit(5)
    ).all()
    return {"average_rating": round(float(avg), 2) if avg is not None else None, "review_count": count, "recent_reviews": recent}


def compare_products(db: Session, args: CompareArgs) -> list[dict]:
    products = [p for pid in dict.fromkeys(args.product_ids) if (p := _active_product(db, pid))]
    return [d.model_dump(mode="json") for d in build_details(db, products)]


TOOLS: dict[str, tuple[type[BaseModel], Callable[[Session, Any], Any]]] = {
    "search_products": (SearchArgs, search_products),
    "get_product_details": (ProductIdArgs, get_product_details),
    "get_inventory": (ProductIdArgs, get_inventory),
    "get_seller_details": (SellerArgs, get_seller_details),
    "get_product_reviews": (ProductIdArgs, get_product_reviews),
    "compare_products": (CompareArgs, compare_products),
}


def call_tool(db: Session, name: str, raw_args: dict) -> Any:
    """Single entry point for LLM-requested tool calls. Unknown tools and invalid arguments raise ValueError."""
    if name not in TOOLS:
        raise ValueError(f"Unknown tool '{name}'")
    schema, fn = TOOLS[name]
    return fn(db, schema.model_validate(raw_args))
