import io
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import segno
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import schemas as sch
from . import services as svc
from .catalog import STICKERS, STICKER_CODES
from .models import Base, engine, SessionLocal, User, Category, Product, Order, OrderSticker, Post
from .security import hash_password, verify_password, make_token, user_id_from_token
from .seed import seed

log = logging.getLogger("smena")
STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)
    seed(demo_orders=os.getenv("SEED_DEMO", "1") == "1")
    yield


app = FastAPI(title="Ночная смена", lifespan=lifespan)

# ---------- ошибки: различаем ввод, доступ и сбой сервера ----------

FIELD_RU = {
    "name": "Имя", "email": "Email", "password": "Пароль", "qty": "Количество", "items": "Состав заказа",
    "comment": "Комментарий", "price": "Цена", "stock": "Остаток", "title": "Заголовок", "body": "Текст",
    "x": "Позиция по горизонтали", "y": "Позиция по вертикали", "rot": "Поворот", "code": "Стикер",
    "stickers": "Стикеры", "description": "Описание", "category_id": "Категория", "product_id": "Напиток",
    "playlist": "Что слушать", "status": "Статус", "days": "Период (дней)", "q": "Поиск", "sort": "Сортировка",
    "glyph": "Иконка",
}
ERR_RU = {
    "missing": "обязательное поле", "string_too_short": "слишком короткое значение",
    "string_too_long": "слишком длинное значение", "string_pattern_mismatch": "неверный формат",
    "greater_than": "значение слишком маленькое", "greater_than_equal": "значение слишком маленькое",
    "less_than": "значение слишком большое", "less_than_equal": "значение слишком большое",
    "int_parsing": "нужно целое число", "int_from_float": "нужно целое число", "int_type": "нужно целое число",
    "float_parsing": "нужно число", "float_type": "нужно число", "too_short": "слишком мало элементов",
    "too_long": "слишком много элементов", "string_type": "нужна строка", "bool_parsing": "нужно да или нет",
}
HTTP_RU = {"Not Found": "Не найдено", "Method Not Allowed": "Метод не поддерживается"}


@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError):
    err = exc.errors()[0]
    kinds = [x for x in err["loc"] if isinstance(x, str) and x not in ("body", "query", "path")]
    if err["type"] == "json_invalid" or not kinds:
        detail = "Запрос составлен неверно: некорректный JSON."
    else:
        field = kinds[-1]
        detail = f"Проверьте поле «{FIELD_RU.get(field, field)}»: {ERR_RU.get(err['type'], 'некорректное значение')}."
    return JSONResponse({"detail": detail, "kind": "input"}, status_code=422)


@app.exception_handler(StarletteHTTPException)
async def on_http_error(request: Request, exc: StarletteHTTPException):
    kind = "auth" if exc.status_code in (401, 403) else ("server" if exc.status_code >= 500 else "input")
    detail = HTTP_RU.get(exc.detail, exc.detail)
    return JSONResponse({"detail": detail, "kind": kind}, status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def on_server_error(request: Request, exc: Exception):
    log.exception("Необработанная ошибка: %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Сбой сервера. Ваши данные в порядке, попробуйте ещё раз чуть позже.",
                         "kind": "server"}, status_code=500)


# ---------- зависимости ----------

def get_db():
    with SessionLocal() as s:
        yield s


def current_user(authorization: str | None = Header(None), s=Depends(get_db)):
    uid = None
    if authorization and authorization.lower().startswith("bearer "):
        uid = user_id_from_token(authorization[7:].strip())
    user = s.get(User, uid) if uid else None
    if not user:
        raise HTTPException(401, "Войдите в аккаунт")
    return user


def admin_only(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Недостаточно прав")
    return user


def public_base(request: Request) -> str:
    return os.getenv("PUBLIC_URL") or str(request.base_url)


# ---------- аккаунты ----------

@app.post("/api/register", status_code=201)
def register(data: sch.RegisterIn, s=Depends(get_db)):
    email = data.email.lower()
    if s.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Этот email уже зарегистрирован")
    user = User(name=data.name, email=email, pw=hash_password(data.password), role="client")
    s.add(user)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        raise HTTPException(409, "Этот email уже зарегистрирован")
    return {"token": make_token(user.id), "user": svc.user_out(user)}


@app.post("/api/login")
def login(data: sch.LoginIn, s=Depends(get_db)):
    user = s.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.pw):
        raise HTTPException(401, "Неверный email или пароль")
    return {"token": make_token(user.id), "user": svc.user_out(user)}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return svc.user_out(user)


# ---------- каталог ----------

@app.get("/api/categories")
def categories(s=Depends(get_db)):
    return [{"id": c.id, "name": c.name, "slug": c.slug} for c in s.query(Category).order_by(Category.id)]


@app.get("/api/products")
def products(category: int | None = None, q: str | None = Query(None, max_length=60),
             sort: str = Query("name", pattern="^(name|price_asc|price_desc)$"), s=Depends(get_db)):
    items = s.query(Product).filter(Product.active.is_(True)).all()
    if category is not None:
        items = [p for p in items if p.category_id == category]
    if q and q.strip():
        needle = q.strip().casefold()  # casefold, потому что LIKE в SQLite не различает регистр только для латиницы
        items = [p for p in items if needle in p.name.casefold() or needle in p.description.casefold()]
    if sort == "price_asc":
        items.sort(key=lambda p: (p.price, p.name))
    elif sort == "price_desc":
        items.sort(key=lambda p: (-p.price, p.name))
    else:
        items.sort(key=lambda p: p.name.casefold())
    return [svc.product_out(p) for p in items]


@app.get("/api/products/{product_id}")
def product_detail(product_id: int, s=Depends(get_db)):
    p = s.get(Product, product_id)
    if not p or not p.active:
        raise HTTPException(404, "Напиток не найден")
    return svc.product_out(p)


@app.get("/api/stickers")
def stickers():
    return STICKERS


# ---------- заказы клиента ----------

@app.post("/api/orders", status_code=201)
def create_order(data: sch.OrderIn, user=Depends(current_user), s=Depends(get_db)):
    return svc.order_out(svc.create_order(s, user, data.items, data.comment))


@app.get("/api/orders/my")
def my_orders(user=Depends(current_user), s=Depends(get_db)):
    rows = s.query(Order).filter(Order.user_id == user.id).order_by(Order.id.desc()).limit(50).all()
    return [svc.order_out(o) for o in rows]


def _own_order(s, order_id, user, allow_admin=True):
    o = s.get(Order, order_id)
    if not o or not (o.user_id == user.id or (allow_admin and user.role == "admin")):
        raise HTTPException(404, "Заказ не найден")
    return o


@app.get("/api/orders/{order_id}")
def order_detail(order_id: int, user=Depends(current_user), s=Depends(get_db)):
    return svc.order_out(_own_order(s, order_id, user))


@app.post("/api/orders/{order_id}/cancel")
def cancel_order(order_id: int, user=Depends(current_user), s=Depends(get_db)):
    o = _own_order(s, order_id, user, allow_admin=False)
    if o.status != "new":
        raise HTTPException(409, "Заказ уже готовится, отменить его нельзя")
    return svc.order_out(svc.change_status(s, o, "cancelled"))


@app.put("/api/orders/{order_id}/stickers")
def set_stickers(order_id: int, data: sch.StickersIn, user=Depends(current_user), s=Depends(get_db)):
    o = _own_order(s, order_id, user, allow_admin=False)
    for st in data.stickers:
        if st.code not in STICKER_CODES:
            raise HTTPException(400, f"Неизвестный стикер «{st.code}»")
    o.stickers = [OrderSticker(code=st.code, x=st.x, y=st.y, rot=st.rot) for st in data.stickers]
    s.commit()
    return svc.order_out(o)


# ---------- публичная страница статуса (по секретной ссылке из QR) ----------

def _by_token(s, token):
    o = s.query(Order).filter(Order.token == token).first()
    if not o:
        raise HTTPException(404, "Заказ не найден")
    return o


@app.get("/api/status/{token}")
def public_status(token: str, s=Depends(get_db)):
    o = _by_token(s, token)
    return {"number": o.id, "status": o.status, "status_label": svc.STATUS_LABEL[o.status],
            "items_count": sum(i.qty for i in o.items), "total": o.total,
            "created": o.created.isoformat(timespec="seconds"), "queue_ahead": svc.queue_ahead(s, o)}


@app.get("/api/status/{token}/qr.svg")
def status_qr(token: str, request: Request, s=Depends(get_db)):
    _by_token(s, token)
    qr = segno.make(svc.status_url(public_base(request), token), error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=5, border=2, dark="#2c2523", light="#ffffff")
    return Response(buf.getvalue(), media_type="image/svg+xml")


# ---------- блог ----------

@app.get("/api/posts")
def posts(s=Depends(get_db)):
    rows = s.query(Post).filter(Post.published.is_(True)).order_by(Post.created.desc(), Post.id.desc()).all()
    return [svc.post_out(p) for p in rows]


@app.get("/api/posts/{post_id}")
def post_detail(post_id: int, s=Depends(get_db)):
    p = s.get(Post, post_id)
    if not p or not p.published:
        raise HTTPException(404, "Запись не найдена")
    return svc.post_out(p, full=True)


# ---------- администратор ----------

def _check_category(s, category_id):
    if not s.get(Category, category_id):
        raise HTTPException(400, "Такой категории нет")


def _check_name_free(s, name, own_id=None):
    for p in s.query(Product).all():
        if p.name.casefold() == name.casefold() and p.id != own_id:
            raise HTTPException(409, "Напиток с таким названием уже есть")


@app.get("/api/admin/products")
def admin_products(_=Depends(admin_only), s=Depends(get_db)):
    return [svc.product_out(p) for p in s.query(Product).order_by(Product.id)]


@app.post("/api/admin/products", status_code=201)
def admin_product_create(data: sch.ProductIn, _=Depends(admin_only), s=Depends(get_db)):
    _check_category(s, data.category_id)
    _check_name_free(s, data.name)
    p = Product(**data.model_dump())
    s.add(p)
    s.commit()
    s.refresh(p)
    return svc.product_out(p)


@app.put("/api/admin/products/{product_id}")
def admin_product_update(product_id: int, data: sch.ProductIn, _=Depends(admin_only), s=Depends(get_db)):
    p = s.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Напиток не найден")
    _check_category(s, data.category_id)
    _check_name_free(s, data.name, own_id=p.id)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    s.commit()
    s.refresh(p)
    return svc.product_out(p)


@app.delete("/api/admin/products/{product_id}")
def admin_product_delete(product_id: int, _=Depends(admin_only), s=Depends(get_db)):
    """Мягкое удаление: напиток скрывается из каталога, история заказов остаётся."""
    p = s.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Напиток не найден")
    p.active = False
    s.commit()
    return {"ok": True}


@app.get("/api/admin/posts")
def admin_posts(_=Depends(admin_only), s=Depends(get_db)):
    rows = s.query(Post).order_by(Post.created.desc(), Post.id.desc()).all()
    return [svc.post_out(p, full=True) for p in rows]


def _check_product(s, product_id):
    if product_id is not None and not s.get(Product, product_id):
        raise HTTPException(400, "Такого напитка нет")


@app.post("/api/admin/posts", status_code=201)
def admin_post_create(data: sch.PostIn, _=Depends(admin_only), s=Depends(get_db)):
    _check_product(s, data.product_id)
    p = Post(**data.model_dump())
    s.add(p)
    s.commit()
    s.refresh(p)
    return svc.post_out(p, full=True)


@app.put("/api/admin/posts/{post_id}")
def admin_post_update(post_id: int, data: sch.PostIn, _=Depends(admin_only), s=Depends(get_db)):
    p = s.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Запись не найдена")
    _check_product(s, data.product_id)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    s.commit()
    s.refresh(p)
    return svc.post_out(p, full=True)


@app.delete("/api/admin/posts/{post_id}")
def admin_post_delete(post_id: int, _=Depends(admin_only), s=Depends(get_db)):
    p = s.get(Post, post_id)
    if not p:
        raise HTTPException(404, "Запись не найдена")
    s.delete(p)
    s.commit()
    return {"ok": True}


@app.get("/api/admin/orders")
def admin_orders(status: str | None = Query(None, max_length=20), _=Depends(admin_only), s=Depends(get_db)):
    q = s.query(Order)
    if status:
        if status not in svc.STATUS_LABEL:
            raise HTTPException(400, "Неизвестный статус заказа")
        q = q.filter(Order.status == status)
    out = []
    for o in q.order_by(Order.id.desc()).limit(200).all():
        d = svc.order_out(o)
        d["customer"] = {"name": o.user.name, "email": o.user.email}
        out.append(d)
    return out


@app.put("/api/admin/orders/{order_id}/status")
def admin_order_status(order_id: int, data: sch.StatusIn, _=Depends(admin_only), s=Depends(get_db)):
    o = s.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Заказ не найден")
    return svc.order_out(svc.change_status(s, o, data.status))


@app.get("/api/admin/stats")
def admin_stats(days: int = Query(30, ge=1, le=365), _=Depends(admin_only), s=Depends(get_db)):
    return svc.stats(s, days)


# ---------- страницы ----------

if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/status", include_in_schema=False)
def status_page():
    return FileResponse(STATIC / "status.html")
