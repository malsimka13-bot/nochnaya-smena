from pydantic import BaseModel, ConfigDict, Field

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MAX_QTY = 20          # штук одного напитка в заказе
MAX_LINES = 20        # позиций в заказе
MAX_STICKERS = 12     # стикеров на одном чеке


class In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class RegisterIn(In):
    name: str = Field(min_length=2, max_length=60)
    email: str = Field(pattern=EMAIL_RE, max_length=120)
    password: str = Field(min_length=6, max_length=72)


class LoginIn(In):
    email: str = Field(max_length=120)
    password: str = Field(max_length=200)


class OrderLineIn(In):
    product_id: int = Field(ge=1)
    qty: int = Field(ge=1, le=MAX_QTY)


class OrderIn(In):
    items: list[OrderLineIn] = Field(min_length=1, max_length=MAX_LINES)
    comment: str = Field("", max_length=200)


class StickerIn(In):
    code: str = Field(max_length=20)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    rot: float = Field(0, ge=-45, le=45)


class StickersIn(In):
    stickers: list[StickerIn] = Field(max_length=MAX_STICKERS)


class StatusIn(In):
    status: str = Field(max_length=20)


class ProductIn(In):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field("", max_length=300)
    category_id: int = Field(ge=1)
    price: int = Field(gt=0, le=100_000)
    stock: int = Field(ge=0, le=10_000)
    glyph: str = Field("cup", max_length=20)
    active: bool = True


class PostIn(In):
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=10, max_length=5000)
    playlist: str = Field("", max_length=500)
    product_id: int | None = Field(None, ge=1)
    published: bool = True
