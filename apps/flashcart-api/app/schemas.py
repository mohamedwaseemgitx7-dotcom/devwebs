"""Request/response models. Inputs are strict and forbid unknown fields, so a JSON object can never be
smuggled in where a string is expected (NoSQL operator injection like {"$gt": ""}, concept #42)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

ObjectIdStr = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{24}$")]
CleanStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Category(StrEnum):
    electronics = "Electronics"
    fashion = "Fashion"
    foods = "Foods"
    furniture = "Furniture"
    tools = "Tools"


class Shipping(StrEnum):
    regular = "regular"
    economic = "economic"
    next_day = "next_day"
    instant = "instant"


class Color(StrEnum):
    red = "red"
    blue = "blue"
    orange = "orange"
    black = "black"
    white = "white"
    green = "green"
    grey = "grey"


SortKey = Literal["rating", "price_asc", "price_desc", "popular", "newest"]


# ---------- auth ----------
class SignupIn(Strict):
    email: EmailStr
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    password: Annotated[str, StringConstraints(min_length=10, max_length=128)]

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        classes = sum(
            [any(c.islower() for c in v), any(c.isupper() for c in v), any(c.isdigit() for c in v),
             any(not c.isalnum() for c in v)]
        )
        if classes < 3:
            raise ValueError("Use at least 3 of: lowercase, uppercase, digits, symbols")
        return v


class LoginIn(Strict):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: Literal["customer", "admin"]


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_in: int
    user: UserOut


# ---------- products ----------
class ProductOut(BaseModel):
    id: str
    sku: str
    slug: str
    name: str
    brand: str
    category: str
    description: str
    price_paise: int
    currency: Literal["INR"] = "INR"
    images: list[str]
    colors: list[str]
    shipping: list[str]
    rating: float
    review_count: int
    sold_count: int
    stock: int
    location: str
    version: int


class ProductPage(BaseModel):
    items: list[ProductOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class FacetCount(BaseModel):
    value: str
    count: int


class Facets(BaseModel):
    categories: list[FacetCount]
    price_min_paise: int
    price_max_paise: int


class ProductCreate(Strict):
    sku: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9-]{3,40}$")]
    name: CleanStr
    brand: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    category: Category
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    price_paise: int = Field(ge=100, le=100_000_000)
    stock: int = Field(ge=0, le=1_000_000)
    images: list[Annotated[str, StringConstraints(pattern=r"^/products/[a-z0-9-]+\.svg$")]] = Field(
        default_factory=list, max_length=6
    )
    colors: list[Color] = Field(default_factory=list, max_length=7)
    shipping: list[Shipping] = Field(default_factory=lambda: [Shipping.regular], min_length=1, max_length=4)
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""
    active: bool = True

    model_config = ConfigDict(extra="forbid", strict=False)  # enums arrive as strings from JSON


class ProductUpdate(Strict):
    """Partial update with optimistic locking: the client must send the version it last saw (#25)."""

    version: int = Field(ge=1)
    name: CleanStr | None = None
    brand: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None = None
    category: Category | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    price_paise: int | None = Field(default=None, ge=100, le=100_000_000)
    images: list[Annotated[str, StringConstraints(pattern=r"^/products/[a-z0-9-]+\.svg$")]] | None = None
    colors: list[Color] | None = None
    shipping: list[Shipping] | None = None
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    active: bool | None = None

    model_config = ConfigDict(extra="forbid", strict=False)


class StockAdjust(Strict):
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


# ---------- cart ----------
class CartItemIn(Strict):
    product_id: ObjectIdStr
    quantity: int = Field(ge=1, le=10)


class CartReplaceIn(Strict):
    items: list[CartItemIn] = Field(max_length=50)


class CartLine(BaseModel):
    product_id: str
    name: str
    image: str | None
    unit_price_paise: int
    quantity: int
    line_total_paise: int
    in_stock: bool
    available: int


class CartOut(BaseModel):
    items: list[CartLine]
    subtotal_paise: int
    shipping_paise: int
    total_paise: int
    item_count: int


# ---------- checkout / orders ----------
class Address(Strict):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    line1: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    postal_code: Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]
    phone: Annotated[str, StringConstraints(pattern=r"^[6-9][0-9]{9}$")]


class CheckoutIn(Strict):
    shipping_address: Address
    shipping_method: Shipping = Shipping.regular
    # Optional: the client may echo the total it displayed so we can tell the user if prices changed.
    expected_total_paise: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid", strict=False)


class OrderItemOut(BaseModel):
    product_id: str
    name: str
    unit_price_paise: int
    quantity: int
    line_total_paise: int


class OrderOut(BaseModel):
    id: str
    order_number: str
    status: str
    items: list[OrderItemOut]
    subtotal_paise: int
    shipping_paise: int
    total_paise: int
    shipping_method: str
    shipping_address: dict
    created_at: datetime
    user_email: str | None = None


class OrderPage(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int


class OrderStatusUpdate(Strict):
    status: Literal["paid", "shipped", "delivered", "cancelled"]


class FavoritesOut(BaseModel):
    product_ids: list[str]
