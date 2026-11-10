from tests.helpers import auth, make_category, make_seller, make_user

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 32


def _upload(client, user, data: bytes, filename="pic.png", content_type="image/png"):
    return client.post("/api/v1/uploads/images", files={"file": (filename, data, content_type)}, headers=auth(user))


def test_seller_uploads_image_and_it_is_served(client, db):
    user, _ = make_seller(db)
    r = _upload(client, user, PNG)
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert url.startswith("/api/v1/media/") and url.endswith(".png")
    served = client.get(url)
    assert served.status_code == 200 and served.content == PNG
    assert served.headers["x-content-type-options"] == "nosniff"


def test_jpeg_and_webp_accepted_with_detected_extension(client, db):
    user, _ = make_seller(db)
    assert _upload(client, user, JPEG, "a.png").json()["url"].endswith(".jpg")  # extension comes from content, not name
    assert _upload(client, user, WEBP, "a.jpg").json()["url"].endswith(".webp")


def test_non_images_rejected_even_with_image_name_and_type(client, db):
    user, _ = make_seller(db)
    assert _upload(client, user, b"<script>alert(1)</script>", "x.png", "image/png").status_code == 415
    assert _upload(client, user, b"<svg xmlns='http://www.w3.org/2000/svg'/>", "x.svg", "image/svg+xml").status_code == 415
    assert _upload(client, user, b"", "empty.png").status_code == 415


def test_oversized_image_rejected(client, db):
    user, _ = make_seller(db)
    assert _upload(client, user, PNG + b"\x00" * (1024 * 1024)).status_code == 413  # limit is 1 MB in tests


def test_only_approved_sellers_can_upload(client, db):
    assert _upload(client, make_user(db, "customer"), PNG).status_code == 403
    pending, _ = make_seller(db, approved=False)
    assert _upload(client, pending, PNG).status_code == 403
    assert client.post("/api/v1/uploads/images", files={"file": ("a.png", PNG, "image/png")}).status_code == 401


def test_media_path_traversal_blocked(client):
    assert client.get("/api/v1/media/../../.env").status_code in (400, 404)
    assert client.get("/api/v1/media/%2e%2e/%2e%2e/.env").status_code in (400, 404)


def test_product_created_with_uploaded_image_and_unsafe_urls_rejected(client, db):
    cat = make_category(db)
    user, _ = make_seller(db)
    url = _upload(client, user, PNG).json()["url"]
    payload = {
        "category_id": cat.id, "name": "Pic Product", "description": "d", "image_urls": [url],
        "variants": [{"sku": "PIC-1", "variant_name": "x", "selling_price": "10", "quantity": 1}],
    }
    r = client.post("/api/v1/products", json=payload, headers=auth(user))
    assert r.status_code == 201 and r.json()["primary_image_url"] == url
    bad = {**payload, "variants": [{**payload["variants"][0], "sku": "PIC-2"}], "image_urls": ["javascript:alert(1)"]}
    assert client.post("/api/v1/products", json=bad, headers=auth(user)).status_code == 422
