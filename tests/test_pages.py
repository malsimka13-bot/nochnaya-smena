from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_index_page_served(c):
    r = c.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Ночная смена" in r.text


def test_status_page_served(c):
    r = c.get("/status", params={"t": "anything"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_static_files_served(c):
    for path in ("/static/css/style.css", "/static/js/main.js", "/static/img/logo.svg"):
        assert c.get(path).status_code == 200, path


def test_every_js_import_points_to_existing_file():
    """Все относительные импорты в модулях фронта должны вести к существующим файлам."""
    import re
    for js in (STATIC / "js").glob("*.js"):
        for target in re.findall(r'from "\./([\w]+\.js)"', js.read_text(encoding="utf-8")):
            assert (STATIC / "js" / target).exists(), f"{js.name} -> {target}"


def test_html_pages_reference_existing_assets():
    import re
    for html in STATIC.glob("*.html"):
        for ref in re.findall(r'(?:src|href)="/static/([^"]+)"', html.read_text(encoding="utf-8")):
            assert (STATIC / ref).exists(), f"{html.name} -> {ref}"
