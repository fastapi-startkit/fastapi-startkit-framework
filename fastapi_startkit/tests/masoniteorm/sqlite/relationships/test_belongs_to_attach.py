from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi_startkit.masoniteorm import BelongsTo


def test_attach_fills_and_creates_unsaved_model():
    relationship = BelongsTo("Bottle", "bottle_id", "id")
    model = MagicMock()
    model.is_created.return_value = False
    model.all_attributes.return_value = {"bottle_id": 7}

    relationship.attach(model, SimpleNamespace(id=7))

    model.fill.assert_called_once_with({"bottle_id": 7})
    model.create.assert_called_once_with({"bottle_id": 7}, cast=True)


def test_attach_updates_saved_model():
    relationship = BelongsTo("Bottle", "bottle_id", "id")
    model = MagicMock()
    model.is_created.return_value = True

    relationship.attach(model, SimpleNamespace(id=3))

    model.update.assert_called_once_with({"bottle_id": 3})
