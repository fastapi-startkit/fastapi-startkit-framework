from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models.caster import Caster

if TYPE_CHECKING:
    from fastapi_startkit.orm.connections.manager import Model


class Attribute:
    # Attributes that are model infrastructure, not data columns.
    # Assignments to these bypass set_attribute() and go straight to __dict__.
    _META_ATTRIBUTES = frozenset({"caster", "connection", "db_manager"})

    __casts__ = {}

    caster: Caster = None

    def __init__(self, attributes: dict = None, **kwargs):
        model: "Model" = self.__class__
        self.caster = Caster(model)

        self._original = {}
        self._attributes = attributes or {}
        self._dirty_attributes = {}

        for key, value in kwargs.items():
            self.set_attribute(key, value)

    def __setattr__(self, key: str, value):
        # Before _dirty_attributes is initialised (early __init__), or for
        # internal/meta attributes, fall back to normal object assignment.
        if key.startswith("_") or key in self._META_ATTRIBUTES or "_dirty_attributes" not in self.__dict__:
            super().__setattr__(key, value)
        else:
            self.set_attribute(key, value)

    def set_attribute(self, key: str, value):
        if key in self.caster.casts:
            value = self.caster.set(key, value)

        if not key.startswith("_"):
            self.__dict__["_dirty_attributes"].update({key: value})

    def set_raw_attributes(self, attributes: dict, sync=False):
        self._attributes = attributes

        if sync:
            self.sync_original()

        return self

    def sync_original(self):
        self._original = self.get_attributes()

    def get_attributes(self):
        return {**self._attributes, **self._dirty_attributes}

    def get_attribute(self, key: str):
        value = None

        if "_attributes" in self.__dict__ and key in self.__dict__["_attributes"]:
            value = self.__dict__["_attributes"][key]

        if "_dirty_attributes" in self.__dict__ and key in self.__dict__["_dirty_attributes"]:
            value = self.__dict__["_dirty_attributes"][key]

        return self.caster.get(key, value)

    def original_is_equivalent(self, key: str) -> bool:
        if key not in self._original:
            return False

        current = self.get_attributes().get(key)
        original = self._original.get(key)

        if current == original:
            return True

        if current is None:
            return False

        # Numeric equivalence (e.g. 1 == "1")
        try:
            return float(current) == float(original)
        except (ValueError, TypeError):
            pass

        return False

    def is_dirty(self) -> bool:
        return bool(self.get_dirty())

    def get_dirty(self) -> dict:
        return {key: value for key, value in self.get_attributes().items() if not self.original_is_equivalent(key)}

    def delete_attribute(self, key: str):
        """Remove a transient attribute that was added during query processing."""
        self._attributes.pop(key, None)
        self._dirty_attributes.pop(key, None)

    def get_attributes_for_insert(self) -> dict:
        # _dirty_attributes already went through set_attribute (casts applied on assignment).
        # _attributes is set raw via new_model_instance, so apply set casts here.
        casted = {k: self.caster.set(k, v) for k, v in self._attributes.items()}
        return {**casted, **self._dirty_attributes}
