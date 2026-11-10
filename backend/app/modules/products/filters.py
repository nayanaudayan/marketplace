"""Hard-constraint SQL filters shared by the catalogue and AI hybrid search.

These are enforced in SQL independently of any relevance score: a product outside the requested budget, out of
stock or missing a required spec can never be returned just because its semantic score is high.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import ColumnElement, Numeric, and_, case, cast, exists, func, select
from sqlalchemy.orm import Session

from app.modules.categories.router import category_and_descendants
from app.modules.inventory.models import Inventory
from app.modules.products.models import Product, ProductVariant, SellerListing
from app.modules.sellers.models import Seller

NUMERIC_TEXT = r"^-?[0-9]+(\.[0-9]+)?$"


@dataclass
class SpecClause:
    key: str
    op: str  # ">=", "<=", "=="
    value: float | bool | str


@dataclass
class ProductFilters:
    category_id: int | None = None
    brand: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool = False
    specs: list[SpecClause] = field(default_factory=list)


def purchasable_listing_exists(
    min_price: Decimal | None = None, max_price: Decimal | None = None, in_stock_only: bool = False
) -> ColumnElement[bool]:
    """EXISTS an active listing, from an approved seller, optionally within a price range / with stock."""
    conds = [
        ProductVariant.product_id == Product.id,
        SellerListing.status == "active",
        Seller.approval_status == "approved",
    ]
    if min_price is not None:
        conds.append(SellerListing.selling_price >= min_price)
    if max_price is not None:
        conds.append(SellerListing.selling_price <= max_price)
    if in_stock_only:
        conds.append(Inventory.available_quantity - Inventory.reserved_quantity > 0)
    return exists(
        select(1)
        .select_from(SellerListing)
        .join(ProductVariant, ProductVariant.id == SellerListing.product_variant_id)
        .join(Seller, Seller.id == SellerListing.seller_id)
        .join(Inventory, Inventory.seller_listing_id == SellerListing.id)
        .where(and_(*conds))
        .correlate(Product)
    )


def spec_clause(spec: SpecClause) -> ColumnElement[bool]:
    """One requirement on a product's JSONB specifications. The key is a bound parameter, never interpolated.
    A product that lacks the field (or stores a non-number where a number is needed) does not satisfy it."""
    raw = Product.specifications[spec.key].astext
    if isinstance(spec.value, bool):
        return raw == ("true" if spec.value else "false")
    if isinstance(spec.value, str):
        return func.lower(raw) == spec.value.lower()
    numeric = case((raw.op("~")(NUMERIC_TEXT), cast(raw, Numeric)))
    return {">=": numeric >= spec.value, "<=": numeric <= spec.value, "==": numeric == spec.value}[spec.op]


def build_filter_clauses(db: Session, f: ProductFilters) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = [
        Product.status == "active",
        purchasable_listing_exists(f.min_price, f.max_price, f.in_stock),
    ]
    if f.category_id is not None:
        clauses.append(Product.category_id.in_(category_and_descendants(db, f.category_id)))
    if f.brand:
        clauses.append(Product.brand.ilike(f.brand))
    clauses.extend(spec_clause(s) for s in f.specs)
    return clauses
