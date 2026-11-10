from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.sellers.models import Seller
from app.modules.users.models import User


def get_seller(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Seller:
    seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seller profile required")
    return seller


def get_approved_seller(seller: Seller = Depends(get_seller)) -> Seller:
    if seller.approval_status != "approved":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seller account is not approved yet")
    return seller
