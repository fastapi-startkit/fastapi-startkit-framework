from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm import BelongsTo, Model

if TYPE_CHECKING:
    from .owners import TypedUser  # noqa: F401


class TypedProfile(Model):
    __table__ = "profiles"
    __timestamps__ = False

    user = BelongsTo["TypedUser"]("TypedUser", "user_id", "id")


class TypedArticle(Model):
    __table__ = "articles"
    __timestamps__ = None


class TypedProduct(Model):
    __table__ = "products"
