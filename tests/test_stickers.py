import pytest

from app import services
from tests.conftest import order_via_api


def _put(c, headers, oid, stickers):
    return c.put(f"/api/orders/{oid}/stickers", json={"stickers": stickers}, headers=headers)


def _st(code="sudo", x=0.5, y=0.5, rot=0):
    return {"code": code, "x": x, "y": y, "rot": rot}


@pytest.fixture
def oid(c, client_h):
    return order_via_api(c, client_h).json()["id"]


def test_save_and_read_back(c, client_h, oid):
    r = _put(c, client_h, oid, [_st("sudo", 0.2, 0.3, 10), _st("heart", 0.8, 0.9, -15)])
    assert r.status_code == 200
    got = c.get(f"/api/orders/{oid}", headers=client_h).json()["stickers"]
    assert got == [{"code": "sudo", "x": 0.2, "y": 0.3, "rot": 10}, {"code": "heart", "x": 0.8, "y": 0.9, "rot": -15}]


def test_new_order_has_no_stickers(c, client_h, oid):
    assert c.get(f"/api/orders/{oid}", headers=client_h).json()["stickers"] == []


def test_put_replaces_previous_set(c, client_h, oid):
    _put(c, client_h, oid, [_st("sudo"), _st("bug"), _st("star")])
    _put(c, client_h, oid, [_st("fire")])
    got = c.get(f"/api/orders/{oid}", headers=client_h).json()["stickers"]
    assert [s["code"] for s in got] == ["fire"]


def test_empty_list_clears_stickers(c, client_h, oid):
    _put(c, client_h, oid, [_st()])
    assert _put(c, client_h, oid, []).status_code == 200
    assert c.get(f"/api/orders/{oid}", headers=client_h).json()["stickers"] == []


@pytest.mark.parametrize("n,code", [(12, 200), (13, 422)])
def test_sticker_count_boundary(c, client_h, oid, n, code):
    assert _put(c, client_h, oid, [_st() for _ in range(n)]).status_code == code


@pytest.mark.parametrize("x,y,ok", [(0, 0, True), (1, 1, True), (1.01, 0.5, False), (-0.01, 0.5, False),
                                    (0.5, 1.01, False), (0.5, -0.01, False)])
def test_position_boundaries(c, client_h, oid, x, y, ok):
    assert (_put(c, client_h, oid, [_st(x=x, y=y)]).status_code == 200) is ok


@pytest.mark.parametrize("rot,ok", [(-45, True), (45, True), (0, True), (45.5, False), (-46, False)])
def test_rotation_boundaries(c, client_h, oid, rot, ok):
    assert (_put(c, client_h, oid, [_st(rot=rot)]).status_code == 200) is ok


def test_unknown_sticker_code_rejected(c, client_h, oid):
    r = _put(c, client_h, oid, [_st("nonexistent")])
    assert r.status_code == 400
    assert r.json()["kind"] == "input"


def test_bad_request_does_not_change_existing_stickers(c, client_h, oid):
    _put(c, client_h, oid, [_st("sudo")])
    _put(c, client_h, oid, [_st("sudo"), _st("nonexistent")])
    got = c.get(f"/api/orders/{oid}", headers=client_h).json()["stickers"]
    assert [s["code"] for s in got] == ["sudo"]


def test_foreign_user_cannot_decorate(c, client_h, other_h, oid):
    assert _put(c, other_h, oid, [_st()]).status_code == 404


def test_admin_cannot_decorate_someone_elses_receipt(c, admin_h, oid):
    assert _put(c, admin_h, oid, [_st()]).status_code == 404


def test_guest_cannot_decorate(c, oid):
    assert c.put(f"/api/orders/{oid}/stickers", json={"stickers": []}).status_code == 401


# ---- QR ----

def test_status_url_builder():
    assert services.status_url("http://127.0.0.1:8000/", "abc") == "http://127.0.0.1:8000/status?t=abc"
    assert services.status_url("http://192.168.0.5:8000", "abc") == "http://192.168.0.5:8000/status?t=abc"


def test_qr_is_svg(c, client_h):
    token = order_via_api(c, client_h).json()["token"]
    r = c.get(f"/api/status/{token}/qr.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in r.text


def test_qr_for_unknown_token_404(c):
    assert c.get("/api/status/nope/qr.svg").status_code == 404
