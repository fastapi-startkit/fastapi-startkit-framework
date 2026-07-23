from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm import MorphTo

class Review(Model):
    __table__ = "reviews"

    reviewable_type: str
    content: str

    reviewable = MorphTo("Review", morph_key="reviewable_type", morph_id="reviewable_id")
