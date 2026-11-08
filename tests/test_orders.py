import pytest

from tests.conftest import pid, stock, order_via_api

FLAT = "sudo flat white"      # 260 руб, остаток 60
ESPRESSO = "kill -9 espresso"  # 160 руб, остаток 80
CROISSANT = "git commit croissant"  # остаток 3
BRIOCHE = "apt install brioche"     # остаток 0


def test_guest_cannot_order(c):
    r = c.post("/api/orders", json={"items": [{"product_id": pid(FLAT), "qty": 1}]})
    assert r.status_code == 401


def test_total_is_calculated_on_server(c, client_h):
    r = order_via_api(c, client_h, [(FLAT, 2), (ESPRESSO, 1)])
    assert r.status_code == 201
    o = r.json()
    assert o["total"] == 2 * 260 + 160
    assert o["status"] == "new"
    assert o["token"]


def test_client_cannot_set_price(c, client_h):
    body = {"items": [{"product_id": pid(FLAT), "qty": 1, "price": 1}], "total": 1}
    r = c.post("/api/orders", json=body, headers=client_h)
    assert r.json()["total"] == 260


@pytest.mark.parametrize("qty,code", [(0, 422), (1, 201), (20, 201), (21, 422), (-1, 422)])
def test_qty_boundaries(c, client_h, qty, code):
    assert order_via_api(c, client_h, [(FLAT, qty)]).status_code == code


def test_empty_order_rejected(c, client_h):
    r = c.post("/api/orders", json={"items": []}, headers=client_h)
    assert r.status_code == 422
    assert r.json()["kind"] == "input"


def test_too_many_lines_rejected(c, client_h):
    items = [{"product_id": i, "qty": 1} for i in range(1, 22)]
    assert c.post("/api/orders", json={"items": items}, headers=client_h).status_code == 422


@pytest.mark.parametrize("n,code", [(200, 201), (201, 422)])
def test_comment_length_boundary(c, client_h, n, code):
    assert order_via_api(c, client_h, comment="я" * n).status_code == code


def test_unknown_product_rejected(c, client_h):
    r = c.post("/api/orders", json={"items": [{"product_id": 99999, "qty": 1}]}, headers=client_h)
    assert r.status_code == 400


def test_sold_out_product_rejected(c, client_h):
    r = order_via_api(c, client_h, [(BRIOCHE, 1)])
    assert r.status_code == 409
    assert "apt install brioche" in r.json()["detail"]


def test_stock_is_decremented(c, client_h):
    before = stock(FLAT)
    order_via_api(c, client_h, [(FLAT, 3)])
    assert stock(FLAT) == before - 3


def test_cannot_order_more_than_stock_and_stock_unchanged(c, client_h):
    r = order_via_api(c, client_h, [(CROISSANT, 4)])
    assert r.status_code == 409
    assert stock(CROISSANT) == 3


def test_can_buy_exactly_remaining_stock_then_sold_out(c, client_h):
    assert order_via_api(c, client_h, [(CROISSANT, 3)]).status_code == 201
    assert stock(CROISSANT) == 0
    assert order_via_api(c, client_h, [(CROISSANT, 1)]).status_code == 409


def test_failed_order_does_not_touch_other_stock(c, client_h):
    before = stock(FLAT)
    r = order_via_api(c, client_h, [(FLAT, 1), (BRIOCHE, 1)])
    assert r.status_code == 409
    assert stock(FLAT) == before


def test_duplicate_lines_are_merged(c, client_h):
    body = {"items": [{"product_id": pid(FLAT), "qty": 2}, {"product_id": pid(FLAT), "qty": 3}]}
    o = c.post("/api/orders", json=body, headers=client_h).json()
    assert len(o["items"]) == 1 and o["items"][0]["qty"] == 5


def test_merged_lines_over_limit_rejected(c, client_h):
    body = {"items": [{"product_id": pid(FLAT), "qty": 15}, {"product_id": pid(FLAT), "qty": 10}]}
    assert c.post("/api/orders", json=body, headers=client_h).status_code == 400


def test_my_orders_only_own(c, client_h, other_h):
    order_via_api(c, client_h)
    order_via_api(c, other_h)
    mine = c.get("/api/orders/my", headers=client_h).json()
    assert len(mine) == 1


def test_foreign_order_hidden(c, client_h, other_h):
    oid = order_via_api(c, client_h).json()["id"]
    assert c.get(f"/api/orders/{oid}", headers=other_h).status_code == 404
    assert c.get(f"/api/orders/{oid}", headers=client_h).status_code == 200


def test_admin_can_open_any_order(c, client_h, admin_h):
    oid = order_via_api(c, client_h).json()["id"]
    assert c.get(f"/api/orders/{oid}", headers=admin_h).status_code == 200


# ---- отмена ----

def test_owner_cancels_new_order_and_stock_returns(c, client_h):
    before = stock(FLAT)
    oid = order_via_api(c, client_h, [(FLAT, 2)]).json()["id"]
    r = c.post(f"/api/orders/{oid}/cancel", headers=client_h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert stock(FLAT) == before


def test_double_cancel_rejected_and_stock_not_doubled(c, client_h):
    before = stock(FLAT)
    oid = order_via_api(c, client_h, [(FLAT, 2)]).json()["id"]
    c.post(f"/api/orders/{oid}/cancel", headers=client_h)
    assert c.post(f"/api/orders/{oid}/cancel", headers=client_h).status_code == 409
    assert stock(FLAT) == before


def test_client_cannot_cancel_brewing_order(c, client_h, admin_h):
    oid = order_via_api(c, client_h).json()["id"]
    c.put(f"/api/admin/orders/{oid}/status", json={"status": "brewing"}, headers=admin_h)
    assert c.post(f"/api/orders/{oid}/cancel", headers=client_h).status_code == 409


def test_cannot_cancel_foreign_order(c, client_h, other_h):
    oid = order_via_api(c, client_h).json()["id"]
    assert c.post(f"/api/orders/{oid}/cancel", headers=other_h).status_code == 404


# ---- статусы (админ) ----

def _set(c, admin_h, oid, status):
    return c.put(f"/api/admin/orders/{oid}/status", json={"status": status}, headers=admin_h)


def test_full_status_flow(c, client_h, admin_h):
    oid = order_via_api(c, client_h).json()["id"]
    for status in ("brewing", "ready", "done"):
        r = _set(c, admin_h, oid, status)
        assert r.status_code == 200 and r.json()["status"] == status


def test_cannot_skip_status(c, client_h, admin_h):
    oid = order_via_api(c, client_h).json()["id"]
    assert _set(c, admin_h, oid, "ready").status_code == 409


def test_unknown_status_rejected(c, client_h, admin_h):
    oid = order_via_api(c, client_h).json()["id"]
    assert _set(c, admin_h, oid, "teleported").status_code == 400


def test_done_is_final(c, client_h, admin_h):
    oid = order_via_api(c, client_h).json()["id"]
    for status in ("brewing", "ready", "done"):
        _set(c, admin_h, oid, status)
    assert _set(c, admin_h, oid, "cancelled").status_code == 409
    assert _set(c, admin_h, oid, "new").status_code == 409


def test_ready_order_cannot_be_cancelled(c, client_h, admin_h):
    oid = order_via_api(c, client_h).json()["id"]
    _set(c, admin_h, oid, "brewing")
    _set(c, admin_h, oid, "ready")
    assert _set(c, admin_h, oid, "cancelled").status_code == 409


def test_admin_cancel_restores_stock(c, client_h, admin_h):
    before = stock(ESPRESSO)
    oid = order_via_api(c, client_h, [(ESPRESSO, 4)]).json()["id"]
    _set(c, admin_h, oid, "brewing")
    assert _set(c, admin_h, oid, "cancelled").status_code == 200
    assert stock(ESPRESSO) == before


def test_status_of_missing_order(c, admin_h):
    assert _set(c, admin_h, 99999, "brewing").status_code == 404


def test_admin_orders_filter(c, client_h, admin_h):
    a = order_via_api(c, client_h).json()["id"]
    order_via_api(c, client_h)
    _set(c, admin_h, a, "brewing")
    brewing = c.get("/api/admin/orders", params={"status": "brewing"}, headers=admin_h).json()
    assert [o["id"] for o in brewing] == [a]
    assert brewing[0]["customer"]["email"] == "client@smena.local"
    assert c.get("/api/admin/orders", params={"status": "bogus"}, headers=admin_h).status_code == 400


# ---- публичная страница статуса ----

def test_public_status_has_no_personal_data(c, client_h):
    o = order_via_api(c, client_h, [(FLAT, 2)]).json()
    r = c.get(f"/api/status/{o['token']}")
    assert r.status_code == 200
    j = r.json()
    assert j["number"] == o["id"] and j["items_count"] == 2 and j["status"] == "new"
    assert "email" not in j and "customer" not in j and "token" not in j


def test_unknown_token_404(c):
    assert c.get("/api/status/nope").status_code == 404


def test_queue_ahead_counts_earlier_unfinished_orders(c, client_h, admin_h):
    first = order_via_api(c, client_h).json()
    order_via_api(c, client_h)
    third = order_via_api(c, client_h).json()
    assert c.get(f"/api/status/{third['token']}").json()["queue_ahead"] == 2
    for status in ("brewing", "ready", "done"):
        _set(c, admin_h, first["id"], status)
    assert c.get(f"/api/status/{third['token']}").json()["queue_ahead"] == 1
    assert c.get(f"/api/status/{first['token']}").json()["queue_ahead"] == 0
