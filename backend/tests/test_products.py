from tests.helpers import auth, make_category, make_product, make_seller, make_user


def _payload(category_id, sku="NEW-1"):
    return {
        "category_id": category_id,
        "name": "Seller Laptop",
        "description": "Created via API",
        "brand": "Acme",
        "specifications": {"ram_gb": 16},
        "image_urls": ["https://example.com/a.png"],
        "variants": [{"sku": sku, "variant_name": "16GB", "selling_price": "45000.00", "quantity": 7}],
    }


def test_customer_cannot_create_product(client, db):
    cat = make_category(db)
    customer = make_user(db, "customer")
    assert client.post("/api/v1/products", json=_payload(cat.id), headers=auth(customer)).status_code == 403


def test_unapproved_seller_cannot_create_product(client, db):
    cat = make_category(db)
    user, _ = make_seller(db, approved=False)
    assert client.post("/api/v1/products", json=_payload(cat.id), headers=auth(user)).status_code == 403


def test_approved_seller_creates_and_it_appears_in_catalogue(client, db):
    cat = make_category(db)
    user, _ = make_seller(db)
    r = client.post("/api/v1/products", json=_payload(cat.id), headers=auth(user))
    assert r.status_code == 201, r.text
    detail = r.json()
    assert detail["in_stock"] and float(detail["min_price"]) == 45000
    assert detail["variants"][0]["listings"][0]["available_quantity"] == 7
    listing = client.get("/api/v1/products", params={"q": "seller laptop"}).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == detail["id"]


def test_duplicate_sku_conflict(client, db):
    cat = make_category(db)
    user, _ = make_seller(db)
    assert client.post("/api/v1/products", json=_payload(cat.id), headers=auth(user)).status_code == 201
    assert client.post("/api/v1/products", json=_payload(cat.id), headers=auth(user)).status_code == 409


def test_seller_cannot_edit_or_archive_another_sellers_product(client, db):
    cat = make_category(db)
    _, owner = make_seller(db)
    other_user, _ = make_seller(db)
    product, _ = make_product(db, owner, cat)
    assert client.put(f"/api/v1/products/{product.id}", json={"name": "Hijacked"}, headers=auth(other_user)).status_code == 403
    assert client.delete(f"/api/v1/products/{product.id}", headers=auth(other_user)).status_code == 403


def test_archived_product_hidden_from_public(client, db):
    cat = make_category(db)
    user, seller = make_seller(db)
    product, _ = make_product(db, seller, cat)
    assert client.delete(f"/api/v1/products/{product.id}", headers=auth(user)).status_code == 204
    assert client.get(f"/api/v1/products/{product.id}").status_code == 404
    assert client.get("/api/v1/products").json()["total"] == 0


def test_catalogue_filters_price_stock_and_category_tree(client, db):
    parent = make_category(db, "Electronics")
    laptops = make_category(db, "Laptops", parent)
    _, seller = make_seller(db)
    make_product(db, seller, laptops, "Cheap", price=30000)
    make_product(db, seller, laptops, "Pricey", price=90000)
    make_product(db, seller, laptops, "Gone", price=40000, qty=0)

    def total(**params):
        return client.get("/api/v1/products", params=params).json()["total"]

    assert total() == 3
    assert total(max_price=50000) == 2
    assert total(max_price=50000, in_stock=True) == 1
    assert total(category_id=parent.id) == 3  # parent category includes descendants
    assert total(min_price=60000) == 1


def test_seller_listing_update_respects_reserved_stock(client, db):
    cat = make_category(db)
    user, seller = make_seller(db)
    _, listing = make_product(db, seller, cat, qty=10)
    r = client.put(f"/api/v1/sellers/listings/{listing.id}", json={"selling_price": "123.50", "available_quantity": 3}, headers=auth(user))
    assert r.status_code == 200 and r.json()["available_quantity"] == 3
    other, _ = make_seller(db)
    assert client.put(f"/api/v1/sellers/listings/{listing.id}", json={"selling_price": "1"}, headers=auth(other)).status_code == 404


def test_one_review_per_user_and_rating_bounds(client, db):
    cat = make_category(db)
    _, seller = make_seller(db)
    product, _ = make_product(db, seller, cat)
    customer = make_user(db)
    url = f"/api/v1/products/{product.id}/reviews"
    assert client.post(url, json={"rating": 6}, headers=auth(customer)).status_code == 422
    assert client.post(url, json={"rating": 5, "review_text": "great"}, headers=auth(customer)).status_code == 201
    assert client.post(url, json={"rating": 4}, headers=auth(customer)).status_code == 409
    assert client.get(f"/api/v1/products/{product.id}").json()["avg_rating"] == 5.0
