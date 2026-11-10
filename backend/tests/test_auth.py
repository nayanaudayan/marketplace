from tests.helpers import PASSWORD, auth, make_user


def _register(client, email="a@test.dev", role="customer"):
    return client.post("/api/v1/auth/register", json={"name": "A", "email": email, "password": PASSWORD, "role": role})


def test_register_login_me(client):
    r = _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "customer" and "password" not in str(body)
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["email"] == "a@test.dev"
    assert client.post("/api/v1/auth/login", json={"email": "A@Test.dev", "password": PASSWORD}).status_code == 200


def test_duplicate_email_and_bad_password(client):
    _register(client)
    assert _register(client).status_code == 409
    assert client.post("/api/v1/auth/login", json={"email": "a@test.dev", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "nobody@test.dev", "password": "whatever12"}).status_code == 401


def test_cannot_self_register_as_admin(client):
    r = client.post("/api/v1/auth/register", json={"name": "A", "email": "x@test.dev", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 422


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    first = _register(client).json()
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    # Reusing the already-rotated token fails and revokes the whole family, including the new token.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second.json()["refresh_token"]}).status_code == 401


def test_access_token_cannot_be_used_as_refresh(client):
    body = _register(client).json()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": body["access_token"]}).status_code == 401


def test_logout_revokes_refresh_token(client):
    body = _register(client).json()
    assert client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401


def test_role_enforcement_on_admin_routes(client, db):
    customer = make_user(db, "customer")
    assert client.get("/api/v1/admin/dashboard", headers=auth(customer)).status_code == 403
    admin = make_user(db, "admin")
    assert client.get("/api/v1/admin/dashboard", headers=auth(admin)).status_code == 200
