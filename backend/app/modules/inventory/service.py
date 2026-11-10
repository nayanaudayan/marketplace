"""Inventory mutations. Callers must hold row locks obtained via lock_inventory() inside their transaction."""
from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Inventory


def lock_inventory(db: Session, listing_ids: Iterable[int]) -> dict[int, Inventory]:
    """SELECT ... FOR UPDATE in a stable order (by id) so concurrent checkouts can't deadlock."""
    rows = db.scalars(
        select(Inventory).where(Inventory.seller_listing_id.in_(list(listing_ids))).order_by(Inventory.id).with_for_update()
    ).all()
    return {r.seller_listing_id: r for r in rows}


def sellable(inv: Inventory) -> int:
    return inv.available_quantity - inv.reserved_quantity


def reserve(inv: Inventory, qty: int, label: str = "item") -> None:
    if sellable(inv) < qty:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Insufficient stock for {label}")
    inv.reserved_quantity += qty


def release(inv: Inventory, qty: int) -> None:
    inv.reserved_quantity = max(inv.reserved_quantity - qty, 0)


def commit_sale(inv: Inventory, qty: int) -> None:
    inv.available_quantity -= qty
    inv.reserved_quantity = max(inv.reserved_quantity - qty, 0)


def restock(inv: Inventory, qty: int) -> None:
    inv.available_quantity += qty
