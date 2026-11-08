"""Бизнес-правила: заказы, статусы, остатки, статистика, сериализация."""
import datetime as dt
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import selectinload

from .models import Category, Order, OrderItem, Product
from .schemas import MAX_QTY

STATUS_LABEL = {
    "new": "Принят",
    "brewing": "Готовится",
    "ready": "Готов, ждёт на стойке",
    "done": "Выдан",
    "cancelled": "Отменён",
}
# Разрешённые переходы. «Готов» уже не отменяется: напиток сделан.
STATUS_FLOW = {
    "new": {"brewing", "cancelled"},
    "brewing": {"ready", "cancelled"},
    "ready": {"done"},
    "done": set(),
    "cancelled": set(),
}


# ---------- сериализация ----------

def user_out(u):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role}


def product_out(p):
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "category_id": p.category_id, "category": p.category.name,
        "price": p.price, "stock": p.stock, "available": p.stock > 0,
        "glyph": p.glyph, "active": p.active,
    }


def order_out(o):
    return {
        "id": o.id, "number": o.id, "token": o.token,
        "status": o.status, "status_label": STATUS_LABEL[o.status],
        "total": o.total, "comment": o.comment, "created": o.created.isoformat(timespec="seconds"),
        "items": [{"product_id": i.product_id, "name": i.name, "price": i.price,
                   "qty": i.qty, "sum": i.price * i.qty} for i in o.items],
        "stickers": [{"code": st.code, "x": st.x, "y": st.y, "rot": st.rot} for st in o.stickers],
    }


def post_out(p, full=False):
    d = {
        "id": p.id, "title": p.title, "created": p.created.isoformat(),
        "summary": p.body if len(p.body) <= 160 else p.body[:157].rstrip() + "...",
        "playlist": [line.strip() for line in p.playlist.splitlines() if line.strip()],
        "product": {"id": p.product.id, "name": p.product.name} if p.product else None,
        "published": p.published,
    }
    if full:
        d["body"] = p.body
    return d


def status_url(base: str, token: str) -> str:
    return f"{base.rstrip('/')}/status?t={token}"


# ---------- заказы ----------

def create_order(s, user, lines, comment):
    """Создаёт заказ. Цены берутся из БД, остатки списываются атомарно."""
    merged = {}
    for line in lines:
        merged[line.product_id] = merged.get(line.product_id, 0) + line.qty
    products = {p.id: p for p in s.query(Product).filter(Product.id.in_(list(merged))).all()}

    items, total = [], 0
    for pid, qty in merged.items():
        p = products.get(pid)
        if p is None or not p.active:
            raise HTTPException(400, f"Товар №{pid} недоступен для заказа")
        if qty > MAX_QTY:
            raise HTTPException(400, f"«{p.name}»: не больше {MAX_QTY} шт. в одном заказе")
        if p.stock < qty:
            left = f"осталось {p.stock}" if p.stock > 0 else "закончился"
            raise HTTPException(409, f"Не хватает «{p.name}»: {left}")
        items.append(OrderItem(product_id=p.id, name=p.name, price=p.price, qty=qty))
        total += p.price * qty

    for pid, qty in merged.items():
        changed = (s.query(Product).filter(Product.id == pid, Product.stock >= qty)
                   .update({Product.stock: Product.stock - qty}, synchronize_session=False))
        if changed != 1:
            s.rollback()
            raise HTTPException(409, "Остаток только что изменился. Обновите каталог и повторите заказ")

    order = Order(user_id=user.id, token=secrets.token_urlsafe(9), status="new",
                  total=total, comment=comment, items=items)
    s.add(order)
    s.commit()
    return order


def _restore_stock(s, order):
    for it in order.items:
        s.query(Product).filter(Product.id == it.product_id).update(
            {Product.stock: Product.stock + it.qty}, synchronize_session=False)


def change_status(s, order, new_status):
    if new_status not in STATUS_LABEL:
        raise HTTPException(400, "Неизвестный статус заказа")
    if new_status not in STATUS_FLOW[order.status]:
        raise HTTPException(409, f"Нельзя перевести заказ из «{STATUS_LABEL[order.status]}» "
                                 f"в «{STATUS_LABEL[new_status]}»")
    if new_status == "cancelled":
        _restore_stock(s, order)
    order.status = new_status
    s.commit()
    return order


def queue_ahead(s, order):
    """Сколько заказов перед этим ещё не готово."""
    if order.status not in ("new", "brewing"):
        return 0
    return (s.query(Order).filter(Order.id < order.id, Order.status.in_(("new", "brewing"))).count())


# ---------- статистика ----------

def stats(s, days):
    today = dt.date.today()
    start = today - dt.timedelta(days=days - 1)
    since = dt.datetime.combine(start, dt.time.min)
    orders = s.query(Order).options(selectinload(Order.items)).filter(Order.created >= since).all()
    prod_cat = {p.id: p.category_id for p in s.query(Product).all()}
    cat_name = {c.id: c.name for c in s.query(Category).all()}

    daily = {start + dt.timedelta(days=i): [0, 0] for i in range(days)}  # [выручка, заказов]
    by_hour = [0] * 24
    top, by_cat = {}, {}
    revenue = n_orders = items_sold = cancelled = 0

    for o in orders:
        if o.status == "cancelled":
            cancelled += 1
            continue
        d = o.created.date()
        if d in daily:
            daily[d][0] += o.total
            daily[d][1] += 1
        by_hour[o.created.hour] += 1
        revenue += o.total
        n_orders += 1
        for it in o.items:
            items_sold += it.qty
            t = top.setdefault(it.product_id, {"name": it.name, "qty": 0, "revenue": 0})
            t["qty"] += it.qty
            t["revenue"] += it.price * it.qty
            cname = cat_name.get(prod_cat.get(it.product_id), "Без категории")
            by_cat[cname] = by_cat.get(cname, 0) + it.price * it.qty

    return {
        "days": days,
        "summary": {"revenue": revenue, "orders": n_orders, "items_sold": items_sold,
                    "avg_check": round(revenue / n_orders) if n_orders else 0, "cancelled": cancelled},
        "daily": [{"date": d.isoformat(), "revenue": v[0], "orders": v[1]} for d, v in daily.items()],
        "top_products": sorted(top.values(), key=lambda t: (-t["qty"], t["name"]))[:5],
        "by_hour": [{"hour": h, "orders": n} for h, n in enumerate(by_hour)],
        "by_category": [{"name": n, "revenue": r} for n, r in
                        sorted(by_cat.items(), key=lambda kv: (-kv[1], kv[0]))],
    }
