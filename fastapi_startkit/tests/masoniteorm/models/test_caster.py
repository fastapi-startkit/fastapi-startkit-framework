from typing import Annotated

import pendulum
import pytest

from fastapi_startkit.carbon import Carbon
from fastapi_startkit.masoniteorm import Field, ModelField
from fastapi_startkit.masoniteorm.models.caster import BaseCast, Caster, DateCast, IntCast
from fastapi_startkit.masoniteorm.models.model import Model


def test_date_cast_set_returns_utc_datetime():
    assert DateCast().set("2024-01-02T03:04:05") == pendulum.datetime(2024, 1, 2, 3, 4, 5, tz="UTC")


def test_date_cast_set_rejects_non_datetime_values():
    with pytest.raises(ValueError, match="Cannot cast"):
        DateCast().set("P1D")


def test_unannotated_model_field_falls_back_to_string_cast():
    with pytest.warns(DeprecationWarning):

        class CasterLegacyProfile(Model):
            address = ModelField()

    assert Caster(CasterLegacyProfile).casts["address"] == "str"


def test_default_factory_supplies_missing_value():
    class CasterTagged(Model):
        tags = Field[list](default_factory=list)

    assert CasterTagged().tags == []


def test_value_set_over_null_original_is_dirty():
    class CasterDirtyProfile(Model):
        nickname: str

    profile = CasterDirtyProfile().set_raw_attributes({"nickname": None}, sync=True)
    profile.nickname = "ace"

    assert profile.get_dirty() == {"nickname": "ace"}


def test_unresolvable_annotation_keeps_resolvable_casts():
    class CasterForwardRefProfile(Model):
        age: int
        owner: "UndefinedOwner"  # noqa: F821  # pyright: ignore[reportUndefinedVariable]

    assert isinstance(Caster(CasterForwardRefProfile).casts["age"], IntCast)


class IsoStringCast(BaseCast):
    def get(self, value):
        return f"get:{value}"

    def set(self, value):
        return f"set:{value}"


class UpperCast(BaseCast):
    def get(self, value):
        return str(value).upper()

    def set(self, value):
        return str(value).lower()


def test_annotated_cast_class_overrides_inherited_column():
    class StampedModel(Model):
        created_at: Annotated[Carbon, IsoStringCast]

    caster = Caster(StampedModel)

    assert caster.casts["created_at"] is IsoStringCast
    assert caster.get("created_at", "x") == "get:x"
    assert caster.set("created_at", "x") == "set:x"
    assert isinstance(caster.casts["updated_at"], DateCast)


def test_annotated_cast_instance_is_used_like_a_class():
    class ShoutingModel(Model):
        name: Annotated[str, UpperCast()]
        nickname: Annotated[str, IsoStringCast()]

    caster = Caster(ShoutingModel)

    assert caster.get("name", "joe") == "JOE"
    assert caster.set("name", "JOE") == "joe"
    assert caster.get("nickname", "j") == "get:j"
    assert caster.set("nickname", "j") == "set:j"


class DuckTypedCast:
    def get(self, value):
        return value

    def set(self, value):
        return value


def test_annotated_without_a_cast_falls_back_to_the_base_type():
    class CountedModel(Model):
        visits: Annotated[int, "not a cast", DuckTypedCast, DuckTypedCast()]

    caster = Caster(CountedModel)

    assert isinstance(caster.casts["visits"], IntCast)
    assert caster.get("visits", "3") == 3
