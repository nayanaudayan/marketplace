import json

import pytest

from app.modules.payments import service as payments
from tests.helpers import auth, make_address, make_category, make_product, make_seller, make_user


@pytest.fixture
def pending_payment(client, db):
    cat = make_category(db)
    _, seller = make_seller(db)
    _, listing = make_product(db, seller, cat, price=500, qty=5)
    buyer = make_user(db)
    addr = make_address(db, buyer)
    h = auth(buyer)
    client.post("/api/v1/cart/items", json={"seller_listing_id": listing.id, "quantity": 2}, headers=h)
    order = client.post("/api/v1/orders", json={"shipping_address_id": addr.id}, headers=h).json()
    pay = client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=h).json()
    from app.modules.payments.models import Payment

    ref = db.get(Payment, pay["payment_id"]).transaction_reference
    return {"order": order, "ref": ref, "headers": h}


def _post_webhook(client, payload: dict, signature: str | None = None):
    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    headers["X-Signature"] = signature if signature is not None else payments.sign(raw)
    return client.post("/api/v1/payments/webhook", content=raw, headers=headers)


def test_webhook_rejects_missing_or_bad_signature(client, pending_payment):
    payload = {"transaction_reference": pending_payment["ref"], "status": "success"}
    assert _post_webhook(client, payload, signature="deadbeef").status_code == 401
    raw = json.dumps(payload).encode()
    assert client.post("/api/v1/payments/webhook", content=raw).status_code == 401
    order = client.get(f"/api/v1/orders/{pending_payment['order']['id']}", headers=pending_payment["headers"]).json()
    assert order["payment_status"] == "pending"


def test_valid_webhook_confirms_order_and_replay_is_idempotent(client, pending_payment):
    payload = {"transaction_reference": pending_payment["ref"], "status": "success", "amount": "1000.00"}
    assert _post_webhook(client, payload).status_code == 200
    assert _post_webhook(client, payload).status_code == 200  # replay: no double deduction, no error
    order = client.get(f"/api/v1/orders/{pending_payment['order']['id']}", headers=pending_payment["headers"]).json()
    assert order["payment_status"] == "paid" and order["order_status"] == "confirmed"


def test_webhook_amount_mismatch_rejected(client, pending_payment):
    payload = {"transaction_reference": pending_payment["ref"], "status": "success", "amount": "1.00"}
    assert _post_webhook(client, payload).status_code == 422
    order = client.get(f"/api/v1/orders/{pending_payment['order']['id']}", headers=pending_payment["headers"]).json()
    assert order["payment_status"] == "pending"


def test_late_success_after_cancellation_never_resurrects_order(client, pending_payment):
    oid = pending_payment["order"]["id"]
    client.post(f"/api/v1/orders/{oid}/cancel", headers=pending_payment["headers"])
    # the pending payment was failed by the cancel, so a late "success" is a no-op and never resurrects the order
    assert _post_webhook(client, {"transaction_reference": pending_payment["ref"], "status": "success"}).status_code == 200
    order = client.get(f"/api/v1/orders/{oid}", headers=pending_payment["headers"]).json()
    assert order["order_status"] == "cancelled"


def test_unknown_reference_404(client):
    assert _post_webhook(client, {"transaction_reference": "txn_nope", "status": "success"}).status_code == 404


def test_other_user_cannot_complete_mock_payment(client, db, pending_payment):
    stranger = make_user(db)
    r = client.post("/api/v1/payments/mock/1/complete", json={"success": True}, headers=auth(stranger))
    assert r.status_code == 404
