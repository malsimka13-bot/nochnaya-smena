import os
import secrets
import tempfile
import datetime as dt
from pathlib import Path

# Переменные окружения задаём ДО импорта приложения
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(tempfile.mkdtemp()) / "test.db").as_posix()
os.environ["PBKDF2_ITERATIONS"] = "1000"  # быстрые хеши только в тестах

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Base, engine, SessionLocal, Order, OrderItem, Product, User
from app.seed import seed


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed(demo_orders=False)
    yield


@pytest.fixture
def c():
    with TestClient(app) as cl:
        yield cl


def login_headers(c, email, password):
    r = c.post("/api/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture
def client_h(c):
    return login_headers(c, "client@smena.local", "client123")


@pytest.fixture
def admin_h(c):
    return login_headers(c, "admin@smena.local", "admin123")


@pytest.fixture
def other_h(c):
    """Второй клиент для проверки чужих заказов."""
    c.post("/api/register", json={"name": "Другой", "email": "other@test.local", "password": "secret1"})
    return login_headers(c, "other@test.local", "secret1")


def pid(name):
    with SessionLocal() as s:
        return s.query(Product).filter(Product.name == name).one().id


def stock(name):
    with SessionLocal() as s:
        return s.query(Product).filter(Product.name == name).one().stock


def make_order(created, status="done", lines=(("sudo flat white", 1),)):
    """Вставляет заказ напрямую в БД с нужной датой (для статистики)."""
    with SessionLocal() as s:
        uid = s.query(User).filter(User.email == "client@smena.local").one().id
        items, total = [], 0
        for name, qty in lines:
            p = s.query(Product).filter(Product.name == name).one()
            items.append(OrderItem(product_id=p.id, name=p.name, price=p.price, qty=qty))
            total += p.price * qty
        o = Order(user_id=uid, token=secrets.token_urlsafe(9),
                  status=status, total=total, created=created, items=items)
        s.add(o)
        s.commit()
        return o.id


def at(days_ago, hour, minute=0):
    d = dt.date.today() - dt.timedelta(days=days_ago)
    return dt.datetime.combine(d, dt.time(hour, minute))


def order_via_api(c, headers, lines=(("sudo flat white", 1),), comment=""):
    body = {"items": [{"product_id": pid(n), "qty": q} for n, q in lines], "comment": comment}
    return c.post("/api/orders", json=body, headers=headers)
