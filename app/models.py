import os
import datetime as dt
from sqlalchemy import create_engine, event, ForeignKey, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

URL = os.getenv("DATABASE_URL", "sqlite:///./nochnaya_smena.db")
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(engine, expire_on_commit=False)

if URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('client','admin')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True, index=True)
    pw: Mapped[str]
    role: Mapped[str] = mapped_column(default="client")  # client | admin


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    slug: Mapped[str] = mapped_column(unique=True)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("price > 0"), CheckConstraint("stock >= 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str] = mapped_column(default="")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    price: Mapped[int]  # целые рубли
    stock: Mapped[int] = mapped_column(default=0)
    glyph: Mapped[str] = mapped_column(default="cup")  # ключ иконки на фронте
    active: Mapped[bool] = mapped_column(default=True)
    category = relationship(Category)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('new','brewing','ready','done','cancelled')"),
        CheckConstraint("total >= 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token: Mapped[str] = mapped_column(unique=True, index=True)  # секрет для QR и страницы статуса
    status: Mapped[str] = mapped_column(default="new")
    total: Mapped[int]
    comment: Mapped[str] = mapped_column(default="")
    created: Mapped[dt.datetime] = mapped_column(default=dt.datetime.now, index=True)
    user = relationship(User)
    items = relationship("OrderItem", cascade="all, delete-orphan", order_by="OrderItem.id")
    stickers = relationship("OrderSticker", cascade="all, delete-orphan", order_by="OrderSticker.id")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("qty > 0"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str]   # снимок названия на момент заказа
    price: Mapped[int]  # снимок цены на момент заказа
    qty: Mapped[int]


class OrderSticker(Base):
    __tablename__ = "order_stickers"
    __table_args__ = (CheckConstraint("x BETWEEN 0 AND 1 AND y BETWEEN 0 AND 1"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    code: Mapped[str]
    x: Mapped[float]  # доля ширины чека, 0..1
    y: Mapped[float]  # доля высоты чека, 0..1
    rot: Mapped[float] = mapped_column(default=0)  # градусы


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    body: Mapped[str]
    playlist: Mapped[str] = mapped_column(default="")  # «что слушать», по строке на трек
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), default=None)
    published: Mapped[bool] = mapped_column(default=True)
    created: Mapped[dt.date] = mapped_column(default=dt.date.today)
    product = relationship(Product)
