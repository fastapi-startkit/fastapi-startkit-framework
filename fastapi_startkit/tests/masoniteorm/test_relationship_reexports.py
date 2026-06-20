import fastapi_startkit.masoniteorm as orm
from fastapi_startkit.masoniteorm import relationships

RELATIONSHIP_CLASSES = [
    "BaseRelationship",
    "BelongsTo",
    "BelongsToMany",
    "HasMany",
    "HasManyThrough",
    "HasOne",
    "HasOneThrough",
    "MorphMany",
    "MorphOne",
    "MorphTo",
    "MorphToMany",
]


def test_relationship_classes_are_reexported_from_root():
    for name in RELATIONSHIP_CLASSES:
        assert hasattr(orm, name), f"{name} is not re-exported from fastapi_startkit.masoniteorm"
        assert name in orm.__all__, f"{name} missing from fastapi_startkit.masoniteorm.__all__"
        assert getattr(orm, name) is getattr(relationships, name), (
            f"{name} re-export is not the same class object as in .relationships"
        )
