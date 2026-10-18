from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm import BelongsToMany, HasMany, HasOne, Model

if TYPE_CHECKING:
    from .related import TypedArticle, TypedProduct, TypedProfile  # noqa: F401


class TypedUser(Model):
    __table__ = "users"

    profile = HasOne["TypedProfile"](foreign_key="user_id", local_key="id")
    articles = HasMany["TypedArticle"](local_key="id", foreign_key="user_id")


class TypedStore(Model):
    __table__ = "stores"

    products = BelongsToMany["TypedProduct"](
        local_foreign_key="store_id",
        other_foreign_key="product_id",
        local_owner_key="id",
        other_owner_key="id",
        with_timestamps=True,
    )
