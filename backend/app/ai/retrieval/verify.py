"""Final authoritative check: price, stock and seller come from the database, never from the LLM or embeddings."""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Inventory
from app.modules.products.models import ProductVariant, SellerListing
from app.modules.sellers.models import Seller


@dataclass
class Offer:
    listing_id: int
    price: Decimal
    stock: int
    seller_name: str
    variant_name: str


def best_offers(
    db: Session,
    product_ids: list[int],
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    require_stock: bool = True,
) -> dict[int, Offer]:
    """Cheapest active, in-stock listing per product that satisfies the price constraints."""
    if not product_ids:
        return {}
    sellable = Inventory.available_quantity - Inventory.reserved_quantity
    stmt = (
        select(ProductVariant.product_id, SellerListing, Seller.store_name, ProductVariant.variant_name, sellable)
        .select_from(SellerListing)
        .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
        .join(Seller, Seller.id == SellerListing.seller_id)
        .join(Inventory, Inventory.seller_listing_id == SellerListing.id)
        .where(
            ProductVariant.product_id.in_(product_ids),
            SellerListing.status == "active",
            Seller.approval_status == "approved",
        )
        .order_by(SellerListing.selling_price, SellerListing.id)
    )
    if require_stock:
        stmt = stmt.where(sellable > 0)
    if min_price is not None:
        stmt = stmt.where(SellerListing.selling_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(SellerListing.selling_price <= max_price)

    offers: dict[int, Offer] = {}
    for pid, listing, store, variant_name, stock in db.execute(stmt):
        offers.setdefault(pid, Offer(listing.id, listing.selling_price, max(stock, 0), store, variant_name))
    return offers
