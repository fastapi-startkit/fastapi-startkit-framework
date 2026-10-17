from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm import BelongsToMany, HasMany, HasOne, Model

if TYPE_CHECKING:
    from .related import TypedArticle, TypedProduct, TypedProfile  # noqa: F401


class TypedUser(Model):
    __table__ = "users"

    profile = HasOne["TypedProfile"]("TypedProfile", "user_id", "id")
    articles = HasMany["TypedArticle"]("TypedArticle", "id", "user_id")
    untyped_profile = HasOne("TypedProfile", "user_id", "id")


class TypedStore(Model):
    __table__ = "stores"

    products = BelongsToMany["TypedProduct"]("TypedProduct", "store_id", "product_id", "id", "id", with_timestamps=True)
