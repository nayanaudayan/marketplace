from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.orders import service
from app.modules.orders.models import Order
from app.modules.orders.schemas import OrderCreateIn, OrderOut
from app.modules.users.models import User

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.create_order(db, user, body.shipping_address_id, body.idempotency_key)


@router.get("", response_model=list[OrderOut])
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Order).options(selectinload(Order.items)).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    ).all()


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.get_order_for_user(db, order_id, user)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = service.get_order_for_user(db, order_id, user)
    if order.user_id != user.id:
        # Admins may view any order but cancellation stays with the owner.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the customer can cancel this order")
    return service.cancel_order(db, order)
