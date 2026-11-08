import datetime as dt
import jwt
import pytest

from app import security


def reg(c, **kw):
    body = {"name": "Анна", "email": "anna@test.local", "password": "secret1"}
    body.update(kw)
    return c.post("/api/register", json=body)


def test_register_ok(c):
    r = reg(c)
    assert r.status_code == 201
    j = r.json()
    assert j["user"]["role"] == "client"
    assert j["token"]
    assert "pw" not in j["user"] and "password" not in j["user"]


@pytest.mark.parametrize("name,ok", [("А", False), ("Ан", True), ("А" * 60, True), ("А" * 61, False), ("   ", False)])
def test_name_boundaries(c, name, ok):
    assert (reg(c, name=name).status_code == 201) is ok


@pytest.mark.parametrize("pw,ok", [("12345", False), ("123456", True), ("a" * 72, True), ("a" * 73, False)])
def test_password_boundaries(c, pw, ok):
    assert (reg(c, password=pw).status_code == 201) is ok


@pytest.mark.parametrize("email", ["abc", "a@b", "a b@c.d", "@x.ru", ""])
def test_bad_email_rejected(c, email):
    assert reg(c, email=email).status_code == 422


def test_duplicate_email_case_insensitive(c):
    assert reg(c).status_code == 201
    r = reg(c, email="ANNA@test.local")
    assert r.status_code == 409
    assert r.json()["kind"] == "input"


def test_login_case_insensitive_email(c):
    reg(c)
    r = c.post("/api/login", json={"email": "Anna@Test.Local", "password": "secret1"})
    assert r.status_code == 200


def test_wrong_password_and_unknown_email_same_message(c):
    reg(c)
    a = c.post("/api/login", json={"email": "anna@test.local", "password": "wrong-pass"})
    b = c.post("/api/login", json={"email": "nobody@test.local", "password": "wrong-pass"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]
    assert a.json()["kind"] == "auth"


def test_me_requires_token(c):
    r = c.get("/api/me")
    assert r.status_code == 401
    assert r.json()["kind"] == "auth"


def test_me_with_token(c, client_h):
    r = c.get("/api/me", headers=client_h)
    assert r.status_code == 200
    assert r.json()["email"] == "client@smena.local"


def test_garbage_token_rejected(c):
    r = c.get("/api/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_expired_token_rejected(c):
    exp = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    token = jwt.encode({"sub": "1", "exp": exp}, security.SECRET, algorithm="HS256")
    assert c.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_signed_with_other_key_rejected(c):
    token = jwt.encode({"sub": "1"}, "x" * 40, algorithm="HS256")
    assert c.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_client_cannot_use_admin_api(c, client_h):
    assert c.get("/api/admin/products", headers=client_h).status_code == 403
    assert c.get("/api/admin/stats", headers=client_h).status_code == 403


def test_guest_cannot_use_admin_api(c):
    assert c.get("/api/admin/products").status_code == 401


def test_admin_can_use_admin_api(c, admin_h):
    assert c.get("/api/admin/products", headers=admin_h).status_code == 200


# ---- хеширование паролей ----

def test_hash_is_salted_and_verifies():
    a, b = security.hash_password("secret1"), security.hash_password("secret1")
    assert a != b
    assert security.verify_password("secret1", a)
    assert not security.verify_password("secret2", a)


@pytest.mark.parametrize("stored", ["", "plain", "a$b$c", "md5$1$00$00", "pbkdf2_sha256$x$zz$zz"])
def test_verify_handles_malformed_hash(stored):
    assert security.verify_password("secret1", stored) is False
