from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.cache import cache_delete
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.modules.categories.models import Category
from app.modules.categories.router import CACHE_KEY, CategoryOut
from app.modules.orders.models import Order
from app.modules.orders.schemas import OrderOut
from app.modules.products.models import Product
from app.modules.sellers.models import Seller
from app.modules.sellers.schemas import SellerOut
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class DashboardOut(BaseModel):
    users: int
    sellers: int
    pending_sellers: int
    products: int
    orders: int
    revenue: Decimal


class AdminSellerOut(SellerOut):
    user_email: str
    user_name: str


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    parent_category_id: int | None = None


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    def count(stmt):
        return db.scalar(stmt) or 0

    return DashboardOut(
        users=count(select(func.count(User.id))),
        sellers=count(select(func.count(Seller.id)).where(Seller.approval_status == "approved")),
        pending_sellers=count(select(func.count(Seller.id)).where(Seller.approval_status == "pending")),
        products=count(select(func.count(Product.id)).where(Product.status == "active")),
        orders=count(select(func.count(Order.id))),
        revenue=db.scalar(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.payment_status == "paid")) or Decimal("0"),
    )


@router.get("/sellers", response_model=list[AdminSellerOut])
def list_sellers(status_filter: str | None = Query(default=None, alias="status"), db: Session = Depends(get_db)):
    stmt = select(Seller, User.email, User.name).join(User, User.id == Seller.user_id).order_by(Seller.created_at.desc())
    if status_filter:
        stmt = stmt.where(Seller.approval_status == status_filter)
    return [
        AdminSellerOut(**SellerOut.model_validate(s).model_dump(), user_email=email, user_name=name)
        for s, email, name in db.execute(stmt)
    ]


def _set_approval(db: Session, seller_id: int, new_status: str) -> Seller:
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seller not found")
    seller.approval_status = new_status
    db.commit()
    return seller


@router.put("/sellers/{seller_id}/approve", response_model=SellerOut)
def approve_seller(seller_id: int, db: Session = Depends(get_db)):
    return _set_approval(db, seller_id, "approved")


@router.put("/sellers/{seller_id}/reject", response_model=SellerOut)
def reject_seller(seller_id: int, db: Session = Depends(get_db)):
    return _set_approval(db, seller_id, "rejected")


@router.get("/orders", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db)):
    return db.scalars(select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc()).limit(500)).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, db: Session = Depends(get_db)):
    if body.parent_category_id is not None and db.get(Category, body.parent_category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown parent category")
    category = Category(**body.model_dump())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Category already exists")
    cache_delete(CACHE_KEY)
    return category
