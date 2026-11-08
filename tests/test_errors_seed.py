import datetime as dt

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.models import Base, engine, SessionLocal, Order, Product, Category, Post, User
from app.seed import seed, DEMO_DAYS


# ---- ошибка ввода, доступа и сбой сервера различаются ----

def test_input_error_is_russian_and_marked_input(c):
    r = c.post("/api/register", json={"name": "Анна", "email": "a@b.ru", "password": "123"})
    assert r.status_code == 422
    j = r.json()
    assert j["kind"] == "input"
    assert "Пароль" in j["detail"] and "коротк" in j["detail"]


def test_missing_field_message(c):
    r = c.post("/api/register", json={"name": "Анна", "password": "secret1"})
    assert r.json()["kind"] == "input" and "Email" in r.json()["detail"]


def test_malformed_json_is_input_error(c):
    r = c.post("/api/login", content="{", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["kind"] == "input"


def test_access_error_is_marked_auth(c):
    r = c.get("/api/me")
    assert r.json()["kind"] == "auth"


def test_not_found_is_marked_input(c):
    r = c.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json() == {"detail": "Не найдено", "kind": "input"}


def test_server_failure_is_marked_server_and_hides_internals(monkeypatch):
    def boom(_user_id):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(main, "make_token", boom)
    with TestClient(app, raise_server_exceptions=False) as cl:
        r = cl.post("/api/login", json={"email": "client@smena.local", "password": "client123"})
    assert r.status_code == 500
    j = r.json()
    assert j["kind"] == "server"
    assert "Сбой сервера" in j["detail"]
    assert "secret internal detail" not in r.text and "Traceback" not in r.text


# ---- сид ----

def test_seed_is_idempotent():
    before = _counts()
    seed(demo_orders=False)
    assert _counts() == before


def test_base_seed_contents():
    with SessionLocal() as s:
        assert s.query(User).count() == 2
        assert s.query(Category).count() == 4
        assert s.query(Product).count() == 13
        assert s.query(Post).count() == 3
        assert s.query(Order).count() == 0
        assert {u.role for u in s.query(User)} == {"admin", "client"}


def _reseed_with_demo():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed(demo_orders=True)


def test_demo_orders_are_consistent():
    _reseed_with_demo()
    now = dt.datetime.now()
    with SessionLocal() as s:
        orders = s.query(Order).all()
        assert len(orders) > 90 * 10
        for o in orders:
            assert o.created <= now
            assert o.created.date() >= dt.date.today() - dt.timedelta(days=DEMO_DAYS - 1)
            assert o.total == sum(i.price * i.qty for i in o.items) and o.items
        assert len({o.token for o in orders}) == len(orders)


def test_demo_orders_respect_opening_hours():
    _reseed_with_demo()
    with SessionLocal() as s:
        hours = {o.created.hour for o in s.query(Order)}
    assert hours <= {16, 17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3}


def test_demo_orders_deterministic_for_past_days():
    def past_count():
        _reseed_with_demo()
        today_start = dt.datetime.combine(dt.date.today(), dt.time.min)
        with SessionLocal() as s:
            return s.query(Order).filter(Order.created < today_start).count()
    assert past_count() == past_count()


def _counts():
    with SessionLocal() as s:
        return (s.query(User).count(), s.query(Product).count(), s.query(Post).count(), s.query(Category).count())
