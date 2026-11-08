import datetime as dt
import random
import secrets

from .catalog import CATEGORIES, PRODUCTS, PRODUCT_WEIGHTS, POSTS
from .models import SessionLocal, User, Category, Product, Order, OrderItem, Post
from .security import hash_password

# Кофейня работает с 16:00 до 04:00. Пик: поздний вечер и полночь.
OPEN_HOURS = [16, 17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3]
HOUR_WEIGHTS = [2, 3, 4, 6, 8, 10, 10, 9, 8, 6, 3, 1]
DEMO_DAYS = 90
DEMO_NAMES = ["Аня", "Макс", "Лена", "Тимур", "Оля", "Ян"]


def seed(demo_orders: bool = True) -> None:
    """Заполняет пустую БД. Если пользователи уже есть, ничего не делает."""
    with SessionLocal() as s:
        if s.query(User).first():
            return
        admin_pw = hash_password("admin123")
        client_pw = hash_password("client123")
        s.add_all([
            User(name="Администратор", email="admin@smena.local", pw=admin_pw, role="admin"),
            User(name="Клиент", email="client@smena.local", pw=client_pw, role="client"),
        ])
        demo_users = []
        if demo_orders:
            demo_users = [User(name=n, email=f"guest{i}@smena.local", pw=client_pw)
                          for i, n in enumerate(DEMO_NAMES, 1)]
            s.add_all(demo_users)

        cats = {name: Category(name=name, slug=slug) for name, slug in CATEGORIES}
        s.add_all(cats.values())
        s.flush()

        products = []
        for name, cat, price, stock, glyph, desc in PRODUCTS:
            products.append(Product(name=name, category_id=cats[cat].id, price=price,
                                    stock=stock, glyph=glyph, description=desc))
        s.add_all(products)
        s.flush()
        by_name = {p.name: p for p in products}

        today = dt.date.today()
        for post in POSTS:
            s.add(Post(title=post["title"], body=post["body"], playlist=post["playlist"],
                       product_id=by_name[post["product"]].id,
                       created=today - dt.timedelta(days=post["days_ago"])))

        if demo_orders:
            _add_demo_orders(s, [u.id for u in demo_users], products)
        s.commit()


def _add_demo_orders(s, user_ids, products) -> None:
    """Заказы за последние 90 дней. Генератор с фиксированным seed: прошлые дни одинаковы при каждом запуске."""
    rng = random.Random(42)
    now = dt.datetime.now()
    today = now.date()
    batch = []
    for back in range(DEMO_DAYS - 1, -1, -1):
        day = today - dt.timedelta(days=back)
        n_orders = rng.randint(14, 30)
        if day.weekday() in (4, 5):  # пятница и суббота
            n_orders = int(n_orders * 1.4)
        for _ in range(n_orders):
            hour = rng.choices(OPEN_HOURS, HOUR_WEIGHTS)[0]
            created = dt.datetime.combine(day, dt.time(hour, rng.randint(0, 59), rng.randint(0, 59)))
            n_lines = rng.choices([1, 2, 3], [5, 3, 1])[0]
            chosen = []
            while len(chosen) < n_lines:
                p = rng.choices(products, PRODUCT_WEIGHTS)[0]
                if p not in chosen:
                    chosen.append(p)
            lines = [(p, rng.choices([1, 2], [8, 2])[0]) for p in chosen]
            user_id = rng.choice(user_ids)
            cancel_roll = rng.random()
            if created > now:  # все случайные числа уже взяты, поэтому последовательность не зависит от времени запуска
                continue
            age = now - created
            if cancel_roll < 0.05:
                status = "cancelled"
            elif age < dt.timedelta(minutes=10):
                status = "new"
            elif age < dt.timedelta(minutes=20):
                status = "brewing"
            elif age < dt.timedelta(minutes=30):
                status = "ready"
            else:
                status = "done"
            batch.append(Order(
                user_id=user_id, token=secrets.token_urlsafe(9), status=status, created=created,
                total=sum(p.price * q for p, q in lines),
                items=[OrderItem(product_id=p.id, name=p.name, price=p.price, qty=q) for p, q in lines],
            ))
    s.add_all(batch)
