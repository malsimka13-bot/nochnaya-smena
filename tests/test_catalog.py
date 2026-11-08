
from app.catalog import PRODUCTS
from app.models import SessionLocal, Product
from tests.conftest import pid


def test_lists_all_active_products(c):
    r = c.get("/api/products")
    assert r.status_code == 200
    assert len(r.json()) == len(PRODUCTS)


def test_sold_out_product_is_listed_but_unavailable(c):
    items = {p["name"]: p for p in c.get("/api/products").json()}
    assert items["apt install brioche"]["stock"] == 0
    assert items["apt install brioche"]["available"] is False
    assert items["sudo flat white"]["available"] is True


def test_inactive_product_hidden(c):
    with SessionLocal() as s:
        s.query(Product).filter(Product.name == "curl bumble").update({"active": False})
        s.commit()
    names = [p["name"] for p in c.get("/api/products").json()]
    assert "curl bumble" not in names
    assert c.get(f"/api/products/{pid('curl bumble')}").status_code == 404


def test_filter_by_category(c):
    cats = {x["name"]: x["id"] for x in c.get("/api/categories").json()}
    r = c.get("/api/products", params={"category": cats["Холодное"]}).json()
    assert {p["name"] for p in r} == {"ping cold-brew", "curl bumble"}


def test_unknown_category_gives_empty_list(c):
    assert c.get("/api/products", params={"category": 9999}).json() == []


def test_search_is_case_insensitive_for_cyrillic(c):
    r = c.get("/api/products", params={"q": "ЛАТТЕ"}).json()  # слово есть только в описании
    assert "cat latte.txt" in [p["name"] for p in r]


def test_search_by_command_name(c):
    r = c.get("/api/products", params={"q": "FLAT"}).json()
    assert [p["name"] for p in r] == ["sudo flat white"]


def test_blank_search_returns_everything(c):
    assert len(c.get("/api/products", params={"q": "   "}).json()) == len(PRODUCTS)


def test_search_length_boundary(c):
    assert c.get("/api/products", params={"q": "a" * 60}).status_code == 200
    assert c.get("/api/products", params={"q": "a" * 61}).status_code == 422


def test_sort_by_price(c):
    asc = [p["price"] for p in c.get("/api/products", params={"sort": "price_asc"}).json()]
    desc = [p["price"] for p in c.get("/api/products", params={"sort": "price_desc"}).json()]
    assert asc == sorted(asc)
    assert desc == sorted(desc, reverse=True)


def test_invalid_sort_rejected(c):
    r = c.get("/api/products", params={"sort": "random"})
    assert r.status_code == 422
    assert r.json()["kind"] == "input"


def test_product_detail_and_404(c):
    p = c.get(f"/api/products/{pid('sudo flat white')}")
    assert p.status_code == 200
    assert p.json()["price"] == 260
    assert c.get("/api/products/99999").status_code == 404


def test_product_id_must_be_integer(c):
    assert c.get("/api/products/abc").status_code == 422


def test_stickers_list(c):
    codes = [s["code"] for s in c.get("/api/stickers").json()]
    assert len(codes) == 8 and "sudo" in codes
