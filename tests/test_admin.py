import pytest

from tests.conftest import at, make_order, pid


def _cat(c):
    return c.get("/api/categories").json()[0]["id"]


def _product(c, **kw):
    body = {"name": "new drink", "description": "тест", "category_id": _cat(c), "price": 100, "stock": 5}
    body.update(kw)
    return body


# ---- напитки ----

def test_create_product(c, admin_h):
    r = c.post("/api/admin/products", json=_product(c), headers=admin_h)
    assert r.status_code == 201
    assert r.json()["name"] == "new drink"
    assert "new drink" in [p["name"] for p in c.get("/api/products").json()]


@pytest.mark.parametrize("price,ok", [(0, False), (-5, False), (1, True), (100_000, True), (100_001, False)])
def test_price_boundaries(c, admin_h, price, ok):
    r = c.post("/api/admin/products", json=_product(c, price=price), headers=admin_h)
    assert (r.status_code == 201) is ok


@pytest.mark.parametrize("stock,ok", [(-1, False), (0, True), (10_000, True), (10_001, False)])
def test_stock_boundaries(c, admin_h, stock, ok):
    r = c.post("/api/admin/products", json=_product(c, stock=stock), headers=admin_h)
    assert (r.status_code == 201) is ok


@pytest.mark.parametrize("name,ok", [("a", False), ("ab", True), ("x" * 60, True), ("x" * 61, False)])
def test_product_name_boundaries(c, admin_h, name, ok):
    r = c.post("/api/admin/products", json=_product(c, name=name), headers=admin_h)
    assert (r.status_code == 201) is ok


def test_price_must_be_integer(c, admin_h):
    assert c.post("/api/admin/products", json=_product(c, price=99.5), headers=admin_h).status_code == 422


def test_duplicate_product_name_rejected(c, admin_h):
    r = c.post("/api/admin/products", json=_product(c, name="SUDO FLAT WHITE"), headers=admin_h)
    assert r.status_code == 409


def test_unknown_category_rejected(c, admin_h):
    assert c.post("/api/admin/products", json=_product(c, category_id=9999), headers=admin_h).status_code == 400


def test_update_product(c, admin_h):
    pid_ = pid("kill -9 espresso")
    r = c.put(f"/api/admin/products/{pid_}", json=_product(c, name="kill -9 espresso", price=175), headers=admin_h)
    assert r.status_code == 200 and r.json()["price"] == 175


def test_update_keeps_own_name_but_not_foreign(c, admin_h):
    pid_ = pid("kill -9 espresso")
    own = c.put(f"/api/admin/products/{pid_}", json=_product(c, name="kill -9 espresso"), headers=admin_h)
    foreign = c.put(f"/api/admin/products/{pid_}", json=_product(c, name="sudo flat white"), headers=admin_h)
    assert own.status_code == 200 and foreign.status_code == 409


def test_update_missing_product(c, admin_h):
    assert c.put("/api/admin/products/99999", json=_product(c), headers=admin_h).status_code == 404


def test_delete_is_soft(c, admin_h):
    pid_ = pid("curl bumble")
    assert c.delete(f"/api/admin/products/{pid_}", headers=admin_h).status_code == 200
    assert "curl bumble" not in [p["name"] for p in c.get("/api/products").json()]
    in_admin = {p["name"]: p for p in c.get("/api/admin/products", headers=admin_h).json()}
    assert in_admin["curl bumble"]["active"] is False


def test_inactive_product_cannot_be_ordered(c, admin_h, client_h):
    pid_ = pid("curl bumble")
    c.delete(f"/api/admin/products/{pid_}", headers=admin_h)
    r = c.post("/api/orders", json={"items": [{"product_id": pid_, "qty": 1}]}, headers=client_h)
    assert r.status_code == 400


def test_client_cannot_create_product(c, client_h):
    assert c.post("/api/admin/products", json=_product(c), headers=client_h).status_code == 403


# ---- блог ----

def _post(**kw):
    body = {"title": "Заголовок", "body": "Текст записи достаточной длины", "playlist": "Группа — Трек"}
    body.update(kw)
    return body


def test_seed_posts_are_public(c):
    posts = c.get("/api/posts").json()
    assert len(posts) == 3
    assert posts[0]["created"] >= posts[-1]["created"]
    assert posts[0]["playlist"] and posts[0]["product"]


def test_create_post_and_read(c, admin_h):
    r = c.post("/api/admin/posts", json=_post(product_id=pid("sudo flat white")), headers=admin_h)
    assert r.status_code == 201
    pid_ = r.json()["id"]
    full = c.get(f"/api/posts/{pid_}").json()
    assert full["body"].startswith("Текст") and full["product"]["name"] == "sudo flat white"
    assert full["playlist"] == ["Группа — Трек"]


@pytest.mark.parametrize("title,ok", [("ab", False), ("abc", True), ("x" * 120, True), ("x" * 121, False)])
def test_post_title_boundaries(c, admin_h, title, ok):
    assert (c.post("/api/admin/posts", json=_post(title=title), headers=admin_h).status_code == 201) is ok


@pytest.mark.parametrize("n,ok", [(9, False), (10, True), (5000, True), (5001, False)])
def test_post_body_boundaries(c, admin_h, n, ok):
    assert (c.post("/api/admin/posts", json=_post(body="я" * n), headers=admin_h).status_code == 201) is ok


def test_post_unknown_product_rejected(c, admin_h):
    assert c.post("/api/admin/posts", json=_post(product_id=9999), headers=admin_h).status_code == 400


def test_draft_hidden_from_public_visible_to_admin(c, admin_h):
    r = c.post("/api/admin/posts", json=_post(published=False), headers=admin_h).json()
    assert r["id"] not in [p["id"] for p in c.get("/api/posts").json()]
    assert c.get(f"/api/posts/{r['id']}").status_code == 404
    assert r["id"] in [p["id"] for p in c.get("/api/admin/posts", headers=admin_h).json()]


def test_update_and_delete_post(c, admin_h):
    pid_ = c.post("/api/admin/posts", json=_post(), headers=admin_h).json()["id"]
    upd = c.put(f"/api/admin/posts/{pid_}", json=_post(title="Новый заголовок"), headers=admin_h)
    assert upd.status_code == 200 and upd.json()["title"] == "Новый заголовок"
    assert c.delete(f"/api/admin/posts/{pid_}", headers=admin_h).status_code == 200
    assert c.get(f"/api/posts/{pid_}").status_code == 404
    assert c.delete(f"/api/admin/posts/{pid_}", headers=admin_h).status_code == 404


def test_client_cannot_write_posts(c, client_h):
    assert c.post("/api/admin/posts", json=_post(), headers=client_h).status_code == 403


# ---- статистика ----

@pytest.fixture
def known_orders():
    make_order(at(0, 22, 30), "done", [("sudo flat white", 2)])      # 520, сегодня
    make_order(at(1, 1, 15), "done", [("kill -9 espresso", 1)])      # 160, вчера
    make_order(at(0, 23, 10), "cancelled", [("sudo flat white", 5)])  # отменён, не считается
    make_order(at(40, 20, 0), "done", [("cat latte.txt", 1)])        # 250, 40 дней назад


def test_stats_summary(c, admin_h, known_orders):
    s = c.get("/api/admin/stats", params={"days": 30}, headers=admin_h).json()["summary"]
    assert s == {"revenue": 680, "orders": 2, "items_sold": 3, "avg_check": 340, "cancelled": 1}


def test_stats_daily_series(c, admin_h, known_orders):
    d = c.get("/api/admin/stats", params={"days": 30}, headers=admin_h).json()["daily"]
    assert len(d) == 30
    assert d[-1]["revenue"] == 520 and d[-1]["orders"] == 1
    assert d[-2]["revenue"] == 160
    assert sum(x["revenue"] for x in d) == 680


def test_stats_by_hour(c, admin_h, known_orders):
    h = c.get("/api/admin/stats", params={"days": 30}, headers=admin_h).json()["by_hour"]
    assert len(h) == 24
    assert h[22]["orders"] == 1 and h[1]["orders"] == 1 and h[23]["orders"] == 0


def test_stats_top_and_category(c, admin_h, known_orders):
    j = c.get("/api/admin/stats", params={"days": 30}, headers=admin_h).json()
    assert j["top_products"][0] == {"name": "sudo flat white", "qty": 2, "revenue": 520}
    assert j["by_category"] == [{"name": "Кофе", "revenue": 680}]


def test_stats_period_includes_older_orders(c, admin_h, known_orders):
    s = c.get("/api/admin/stats", params={"days": 60}, headers=admin_h).json()["summary"]
    assert s["orders"] == 3 and s["revenue"] == 930


def test_stats_one_day_window(c, admin_h, known_orders):
    j = c.get("/api/admin/stats", params={"days": 1}, headers=admin_h).json()
    assert len(j["daily"]) == 1 and j["summary"]["revenue"] == 520


@pytest.mark.parametrize("days,code", [(0, 422), (1, 200), (365, 200), (366, 422), (-3, 422)])
def test_stats_days_boundaries(c, admin_h, days, code):
    assert c.get("/api/admin/stats", params={"days": days}, headers=admin_h).status_code == code


def test_stats_on_empty_db(c, admin_h):
    s = c.get("/api/admin/stats", headers=admin_h).json()
    assert s["summary"] == {"revenue": 0, "orders": 0, "items_sold": 0, "avg_check": 0, "cancelled": 0}
    assert len(s["daily"]) == 30 and s["top_products"] == []
