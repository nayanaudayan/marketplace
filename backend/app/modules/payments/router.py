import json
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.orders import service as orders
from app.modules.orders.schemas import OrderOut
from app.modules.payments import service
from app.modules.payments.models import Payment
from app.modules.users.models import User

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentOut(BaseModel):
    payment_id: int
    provider: str
    status: str
    amount: Decimal


class CompleteIn(BaseModel):
    success: bool


class WebhookEvent(BaseModel):
    transaction_reference: str
    status: Literal["success", "failed"]
    amount: Decimal | None = None


@router.post("/orders/{order_id}/initiate", response_model=PaymentOut)
def initiate_payment(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = orders.get_order_for_user(db, order_id, user)
    if order.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the customer can pay for this order")
    payment = service.initiate(db, order)
    return PaymentOut(payment_id=payment.id, provider=payment.provider, status=payment.status, amount=payment.amount)


@router.post("/mock/{payment_id}/complete", response_model=OrderOut)
def mock_complete(payment_id: int, body: CompleteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dev-only gateway simulator. It feeds the same server-side path as the real webhook."""
    if settings.is_production:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    orders.get_order_for_user(db, payment.order_id, user)  # ownership check (404 if not theirs)
    return service.process_event(db, payment.transaction_reference, "success" if body.success else "failed")


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if not service.verify_signature(raw, request.headers.get("X-Signature")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")
    try:
        event = WebhookEvent.model_validate(json.loads(raw))
    except (ValueError, ValidationError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Malformed event")
    await run_in_threadpool(service.process_event, db, event.transaction_reference, event.status, event.amount)
    return {"received": True}
