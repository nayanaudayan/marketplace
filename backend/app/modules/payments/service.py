import hashlib
import hmac
import logging
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.modules.orders import service as orders
from app.modules.orders.models import Order
from app.modules.payments.models import Payment

log = logging.getLogger(__name__)


def sign(body: bytes) -> str:
    return hmac.new(settings.payment_webhook_secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: str | None) -> bool:
    return bool(signature) and hmac.compare_digest(sign(body), signature)


def initiate(db: Session, order: Order) -> Payment:
    """Creates (or reuses) a pending payment attempt. Allowed while the order is unpaid and not cancelled."""
    if order.order_status != "pending" or order.payment_status == "paid":
        raise HTTPException(status.HTTP_409_CONFLICT, "Order is not awaiting payment")
    pending = db.scalar(select(Payment).where(Payment.order_id == order.id, Payment.status == "pending"))
    if pending:
        return pending
    payment = Payment(
        order_id=order.id,
        provider="mock",
        transaction_reference=f"txn_{uuid.uuid4().hex}",
        amount=order.total_amount,
    )
    order.payment_status = "pending"  # a retry after a failed attempt
    db.add(payment)
    db.commit()
    return payment


def process_event(db: Session, transaction_reference: str, outcome: str, amount: Decimal | None = None) -> Order:
    """The single trusted path for payment results (webhook and the dev simulator both end here).
    Idempotent: replays of an already-finalised payment are no-ops."""
    payment = db.scalar(select(Payment).where(Payment.transaction_reference == transaction_reference).with_for_update())
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown payment")
    order = db.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == payment.order_id).with_for_update(of=Order)
    )
    if payment.status != "pending":
        return order
    if amount is not None and Decimal(amount) != payment.amount:
        log.warning("payment %s amount mismatch: got %s expected %s", transaction_reference, amount, payment.amount)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Amount mismatch")

    if outcome == "success":
        if order.order_status == "pending":
            payment.status = "succeeded"
            orders.confirm_paid(db, order)
        else:
            # Paid after the order was cancelled/expired: money must go back.
            payment.status = "refunded"
            order.payment_status = "refunded"
            log.warning("payment %s succeeded for %s order %s; refunded", transaction_reference, order.order_status, order.id)
    else:
        payment.status = "failed"
        if order.order_status == "pending":
            order.payment_status = "failed"  # reservation is kept so the customer can retry until it expires
    db.commit()
    return order
