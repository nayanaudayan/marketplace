from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.products.models import Product
from app.modules.products.schemas import ProductCard
from app.modules.products.service import build_cards
from app.modules.users.models import User
from app.modules.wishlist.models import WishlistItem

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[ProductCard])
def get_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    products = db.scalars(
        select(Product)
        .join(WishlistItem, WishlistItem.product_id == Product.id)
        .where(WishlistItem.user_id == user.id, Product.status == "active")
        .order_by(WishlistItem.created_at.desc())
    ).all()
    return build_cards(db, products)


@router.post("/{product_id}", status_code=204)
def add_to_wishlist(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None or product.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    db.execute(
        insert(WishlistItem).values(user_id=user.id, product_id=product_id).on_conflict_do_nothing(constraint="uq_wishlist_user_product")
    )
    db.commit()
    return Response(status_code=204)


@router.delete("/{product_id}", status_code=204)
def remove_from_wishlist(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(WishlistItem).where(WishlistItem.user_id == user.id, WishlistItem.product_id == product_id))
    db.commit()
    return Response(status_code=204)
