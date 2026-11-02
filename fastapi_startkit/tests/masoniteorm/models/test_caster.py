import datetime
from typing import Annotated, Optional, Union

import pendulum
import pytest

from fastapi_startkit.carbon import Carbon
from fastapi_startkit.masoniteorm import Field, ModelField
from fastapi_startkit.masoniteorm.models.caster import (
    BaseCast,
    BoolCast,
    Caster,
    DateCast,
    FloatCast,
    IntCast,
    JsonCast,
)
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


class NullableProfile(Model):
    pipe_int: int | None
    optional_int: Optional[int]
    union_int: Union[int, None]
    none_first: None | int
    ratio: float | None
    active: bool | None
    born_at: datetime.datetime | None
    meta: dict | None
    plain_bool: bool
    plain_dict: dict


@pytest.mark.parametrize(
    ("field", "cast_class"),
    [
        ("pipe_int", IntCast),
        ("optional_int", IntCast),
        ("union_int", IntCast),
        ("none_first", IntCast),
        ("ratio", FloatCast),
        ("active", BoolCast),
        ("born_at", DateCast),
        ("meta", JsonCast),
    ],
)
def test_nullable_annotation_infers_the_inner_cast(field, cast_class):
    caster = Caster(NullableProfile)

    assert isinstance(caster.casts[field], cast_class)
    assert field in caster.nullable


@pytest.mark.parametrize("field", ["pipe_int", "ratio", "active", "born_at", "meta"])
def test_nullable_field_keeps_none_on_get_and_set(field):
    caster = Caster(NullableProfile)

    assert caster.get(field, None) is None
    assert caster.set(field, None) is None


def test_nullable_field_casts_present_values():
    caster = Caster(NullableProfile)

    assert caster.get("pipe_int", "1") == 1
    assert caster.get("ratio", "0.5") == 0.5
    assert caster.get("active", 0) is False
    assert caster.get("born_at", "2026-10-31") == pendulum.datetime(2026, 10, 31)
    assert caster.set("meta", {"a": 1}) == '{"a": 1}'


def test_bare_annotations_keep_their_none_behaviour():
    caster = Caster(NullableProfile)

    assert "plain_bool" not in caster.nullable
    assert caster.get("plain_bool", None) is False
    assert caster.set("plain_dict", None) is None


def test_annotated_nullable_type_infers_the_inner_cast():
    class AnnotatedNullableProfile(Model):
        outer: Annotated[int | None, "metadata"]
        inner: Optional[Annotated[int, "metadata"]]

    caster = Caster(AnnotatedNullableProfile)

    assert isinstance(caster.casts["outer"], IntCast)
    assert isinstance(caster.casts["inner"], IntCast)
    assert caster.nullable >= {"outer", "inner"}


def test_declared_cast_in_optional_annotated_is_kept_and_nullable():
    class DeclaredNullableProfile(Model):
        nickname: Optional[Annotated[str, UpperCast()]]

    caster = Caster(DeclaredNullableProfile)

    assert caster.get("nickname", "joe") == "JOE"
    assert caster.get("nickname", None) is None


def test_multi_type_union_passes_values_through():
    class MixedProfile(Model):
        code: int | str
        maybe_code: int | str | None

    caster = Caster(MixedProfile)

    assert caster.get("code", 1) == 1
    assert caster.get("code", "a1") == "a1"
    assert caster.set("code", 1) == 1
    assert caster.get("maybe_code", None) is None
    assert "maybe_code" in caster.nullable


def test_nullable_field_default_applies_to_none():
    class DefaultedProfile(Model):
        level = Field[int | None](default=1)

    caster = Caster(DefaultedProfile)

    assert isinstance(caster.casts["level"], IntCast)
    assert caster.get("level", None) == 1
    assert caster.get("level", "5") == 5


@pytest.mark.parametrize("annotation", [list, dict, list[float], dict[str, int], list[float] | None])
def test_list_and_dict_annotations_cast_as_json(annotation):
    class CasterJsonDocument(Model):
        payload: annotation  # pyright: ignore[reportInvalidTypeForm]

    cast = Caster(CasterJsonDocument).casts["payload"]

    assert isinstance(cast, JsonCast)
    assert cast.get("[0.1, 0.2]") == [0.1, 0.2]


def test_json_cast_stores_none_as_sql_null():
    class CasterVectorDocument(Model):
        embedding: list[float]

    assert Caster(CasterVectorDocument).set("embedding", None) is None
