from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from app.core.database import SessionLocal
from app.modules.inventory.models import Inventory
from app.modules.orders import service as orders
from app.modules.users.models import User
from tests.helpers import auth, make_address, make_category, make_product, make_seller, make_user


@pytest.fixture
def shop(db):
    cat = make_category(db)
    seller_user, seller = make_seller(db)
    product, listing = make_product(db, seller, cat, price=1000, qty=5)
    buyer = make_user(db)
    return {"seller_user": seller_user, "listing": listing, "buyer": buyer, "address": make_address(db, buyer)}


def _cart_add(client, user, listing_id, qty=1):
    return client.post("/api/v1/cart/items", json={"seller_listing_id": listing_id, "quantity": qty}, headers=auth(user))


def _order(client, shop, key=None):
    body = {"shipping_address_id": shop["address"].id}
    if key:
        body["idempotency_key"] = key
    return client.post("/api/v1/orders", json=body, headers=auth(shop["buyer"]))


def _stock(db, listing_id):
    db.expire_all()
    inv = db.query(Inventory).filter_by(seller_listing_id=listing_id).one()
    return inv.available_quantity, inv.reserved_quantity


def test_cannot_add_more_than_stock(client, shop):
    assert _cart_add(client, shop["buyer"], shop["listing"].id, 6).status_code == 409
    assert _cart_add(client, shop["buyer"], shop["listing"].id, 5).status_code == 200


def test_seller_cannot_buy_own_listing(client, shop):
    assert _cart_add(client, shop["seller_user"], shop["listing"].id).status_code == 403


def test_order_reserves_then_payment_deducts(client, db, shop):
    _cart_add(client, shop["buyer"], shop["listing"].id, 2)
    order = _order(client, shop).json()
    assert order["total_amount"] == "2000.00" and order["order_status"] == "pending"
    assert _stock(db, shop["listing"].id) == (5, 2)
    assert client.get("/api/v1/cart", headers=auth(shop["buyer"])).json()["items"] == []

    pay = client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=auth(shop["buyer"])).json()
    done = client.post(f"/api/v1/payments/mock/{pay['payment_id']}/complete", json={"success": True}, headers=auth(shop["buyer"])).json()
    assert done["payment_status"] == "paid" and done["order_status"] == "confirmed"
    assert _stock(db, shop["listing"].id) == (3, 0)


def test_failed_payment_keeps_reservation_and_allows_retry(client, db, shop):
    _cart_add(client, shop["buyer"], shop["listing"].id, 1)
    order = _order(client, shop).json()
    h = auth(shop["buyer"])
    p1 = client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=h).json()
    failed = client.post(f"/api/v1/payments/mock/{p1['payment_id']}/complete", json={"success": False}, headers=h).json()
    assert failed["payment_status"] == "failed" and failed["order_status"] == "pending"
    assert _stock(db, shop["listing"].id) == (5, 1)
    p2 = client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=h).json()
    assert p2["payment_id"] != p1["payment_id"]
    ok = client.post(f"/api/v1/payments/mock/{p2['payment_id']}/complete", json={"success": True}, headers=h).json()
    assert ok["order_status"] == "confirmed"


def test_cancel_unpaid_releases_and_cancel_paid_restocks(client, db, shop):
    h = auth(shop["buyer"])
    _cart_add(client, shop["buyer"], shop["listing"].id, 2)
    o1 = _order(client, shop).json()
    assert client.post(f"/api/v1/orders/{o1['id']}/cancel", headers=h).json()["order_status"] == "cancelled"
    assert _stock(db, shop["listing"].id) == (5, 0)

    _cart_add(client, shop["buyer"], shop["listing"].id, 2)
    o2 = _order(client, shop).json()
    pay = client.post(f"/api/v1/payments/orders/{o2['id']}/initiate", headers=h).json()
    client.post(f"/api/v1/payments/mock/{pay['payment_id']}/complete", json={"success": True}, headers=h)
    assert _stock(db, shop["listing"].id) == (3, 0)
    cancelled = client.post(f"/api/v1/orders/{o2['id']}/cancel", headers=h).json()
    assert cancelled["order_status"] == "cancelled" and cancelled["payment_status"] == "refunded"
    assert _stock(db, shop["listing"].id) == (5, 0)
    # a cancelled order cannot be paid or cancelled again
    assert client.post(f"/api/v1/payments/orders/{o2['id']}/initiate", headers=h).status_code == 409
    assert client.post(f"/api/v1/orders/{o2['id']}/cancel", headers=h).status_code == 409


def test_idempotency_key_prevents_duplicate_orders(client, db, shop):
    _cart_add(client, shop["buyer"], shop["listing"].id, 1)
    first = _order(client, shop, key="abc").json()
    second = _order(client, shop, key="abc")
    assert second.json()["id"] == first["id"]
    assert _stock(db, shop["listing"].id) == (5, 1)


def test_empty_cart_and_foreign_address_rejected(client, db, shop):
    assert _order(client, shop).status_code == 422
    _cart_add(client, shop["buyer"], shop["listing"].id, 1)
    stranger_addr = make_address(db, make_user(db))
    r = client.post("/api/v1/orders", json={"shipping_address_id": stranger_addr.id}, headers=auth(shop["buyer"]))
    assert r.status_code == 422


def test_users_cannot_see_each_others_orders(client, db, shop):
    _cart_add(client, shop["buyer"], shop["listing"].id, 1)
    order = _order(client, shop).json()
    assert client.get(f"/api/v1/orders/{order['id']}", headers=auth(make_user(db))).status_code == 404


def test_seller_fulfilment_flow(client, db, shop):
    h = auth(shop["buyer"])
    _cart_add(client, shop["buyer"], shop["listing"].id, 1)
    order = _order(client, shop).json()
    seller_h = auth(shop["seller_user"])
    # cannot ship before payment
    assert client.put(f"/api/v1/sellers/orders/{order['id']}/status", json={"order_status": "shipped"}, headers=seller_h).status_code == 409
    pay = client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=h).json()
    client.post(f"/api/v1/payments/mock/{pay['payment_id']}/complete", json={"success": True}, headers=h)
    assert client.put(f"/api/v1/sellers/orders/{order['id']}/status", json={"order_status": "delivered"}, headers=seller_h).status_code == 409
    assert client.put(f"/api/v1/sellers/orders/{order['id']}/status", json={"order_status": "shipped"}, headers=seller_h).json()["order_status"] == "shipped"
    assert client.put(f"/api/v1/sellers/orders/{order['id']}/status", json={"order_status": "delivered"}, headers=seller_h).json()["order_status"] == "delivered"
    # shipped goods can't be cancelled
    assert client.post(f"/api/v1/orders/{order['id']}/cancel", headers=h).status_code == 409
    # another seller can't touch it
    other, _ = make_seller(db)
    assert client.put(f"/api/v1/sellers/orders/{order['id']}/status", json={"order_status": "shipped"}, headers=auth(other)).status_code == 404


def test_concurrent_checkouts_never_oversell(db):
    cat = make_category(db)
    _, seller = make_seller(db)
    _, listing = make_product(db, seller, cat, price=100, qty=3)
    buyers = []
    for _ in range(8):
        u = make_user(db)
        addr = make_address(db, u)
        from app.modules.cart.models import Cart, CartItem

        cart = Cart(user_id=u.id)
        db.add(cart)
        db.flush()
        db.add(CartItem(cart_id=cart.id, seller_listing_id=listing.id, quantity=1))
        db.commit()
        buyers.append((u.id, addr.id))

    def attempt(args):
        user_id, addr_id = args
        with SessionLocal() as session:
            try:
                orders.create_order(session, session.get(User, user_id), addr_id, None)
                return True
            except HTTPException as exc:
                assert exc.status_code == 409
                return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, buyers))

    assert sum(results) == 3
    assert _stock(db, listing.id) == (3, 3)
