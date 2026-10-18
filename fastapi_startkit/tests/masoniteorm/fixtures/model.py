from datetime import datetime, timedelta, time, date

from fastapi_startkit.carbon.carbon import Carbon
from tests.masoniteorm.fixtures.casts import Address
from fastapi_startkit.masoniteorm import Field
from fastapi_startkit.masoniteorm import (
    HasOne,
    BelongsTo,
    HasMany,
    HasManyThrough,
    BelongsToMany,
    HasOneThrough,
    MorphTo,
)
from fastapi_startkit.masoniteorm import Model


class User(Model):
    id = Field[int]()
    name = Field[str]()
    email = Field[str]()
    email_verified_at: datetime
    date_of_birth: date
    session_duration: timedelta
    punch_in_time: time = Field(default=time(12, 0, 0))
    is_admin = Field(default=False)
    preferences: dict
    address = Field[Address]()

    profile: "Profile" = HasOne["Profile"](foreign_key="user_id", local_key="id")
    articles: "Articles" = HasMany["Articles"](local_key="id", foreign_key="user_id")
    logos: "Logo" = HasManyThrough(
        ["Logo", "Articles"],
        "user_id",  # FK on Articles → User  (intermediate.local_key, used in WHERE)
        "id",  # PK on Articles         (intermediate.foreign_key, join left side)
        "id",  # PK on User             (owner.local_owner_key, WHERE value)
        "article_id",  # FK on Logo → Articles  (distant.other_owner_key, join right side)
    )

    def get_is_admin(self) -> bool:
        return self.is_admin


class Profile(Model):
    __table__ = "profiles"
    __timestamps__ = False


class Logo(Model):
    __table__ = "logos"
    __timestamps__ = None

    published_date: Carbon = Field(json_schema_extra={"format": "YYYY-MM-DD HH:mm:ss"})


class Articles(Model):
    __table__ = "articles"
    __timestamps__ = None
    published_date: Carbon = Field(json_schema_extra={"format": "YYYY-MM-DD HH:mm:ss"})

    logo: "Logo" = BelongsTo["Logo"](local_key="id", foreign_key="article_id")
    likes: "Like" = HasMany["Like"](local_key="id", foreign_key="likeable_id")


class Store(Model):
    products: "Product" = BelongsToMany["Product"](
        local_foreign_key="store_id",
        other_foreign_key="product_id",
        local_owner_key="id",
        other_owner_key="id",
        with_timestamps=True,
    )
    products_table: "Product" = BelongsToMany["Product"](
        local_foreign_key="store_id",
        other_foreign_key="product_id",
        local_owner_key="id",
        other_owner_key="id",
        table="product_table",
    )
    store_products: "Product" = BelongsToMany["Product"]()


class Product(Model):
    __table__ = "products"

    likes: "Like" = HasMany["Like"](local_key="id", foreign_key="likeable_id")


class Like(Model):
    __table__ = "likes"

    record: "Model" = MorphTo("Like", "likeable_type", "likeable_id")


class Port(Model):
    __table__ = "ports"
    __connection__ = "dev"


class Country(Model):
    __table__ = "countries"
    __connection__ = "dev"


class IncomingShipment(Model):
    __table__ = "incoming_shipments"
    __connection__ = "dev"

    from_country: "Country" = HasOneThrough(
        ["Country", "Port"],
        "from_port_id",  # FK on IncomingShipment → Port
        "port_country_id",  # FK on Port → Country
        "port_id",  # PK on Port
        "country_id",  # PK on Country
    )
