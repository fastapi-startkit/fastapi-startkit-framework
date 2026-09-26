import pytest

from fastapi_startkit.masoniteorm import Field, ModelField
from fastapi_startkit.masoniteorm.models.caster import Caster, DateCast
from fastapi_startkit.masoniteorm.models.model import Model


def test_date_cast_set_formats_datetime_string():
    assert DateCast().set("2024-01-02T03:04:05") == "2024-01-02 03:04:05"


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
