from __future__ import annotations
import inflection

from typing import TYPE_CHECKING

from fastapi_startkit.carbon import Carbon
from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.models.fields import CreatedAtField, UpdatedAtField
from fastapi_startkit.masoniteorm.models.registry import Registry
from fastapi_startkit.masoniteorm.observers import ObservesEvents
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.models.attribute import Attribute
from fastapi_startkit.masoniteorm.models.relationship import Relationship

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.models.builder import QueryBuilder


class Model(Attribute, Relationship, ObservesEvents):
    db_manager: "DatabaseManager" = None
    __table__ = None
    __primary_key__ = "id"
    __timestamps__ = True
    __incrementing__ = True

    __has_events__ = True
    __observers__ = {}

    __fillable__: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Registry.register(cls)

        fillable = []
        for name, _typ in cls.__annotations__.items():
            attr = getattr(cls, name, None)
            from fastapi_startkit.masoniteorm.relationships.BaseRelationship import (
                BaseRelationship,
            )

            if isinstance(attr, BaseRelationship):
                continue
            if callable(attr):
                continue
            fillable.append(name)
        cls.__fillable__ = fillable

    created_at: Carbon = CreatedAtField(fmt="%Y-%m-%d %H:%M:%S", tz="UTC")
    updated_at: Carbon = UpdatedAtField(fmt="%Y-%m-%d %H:%M:%S", tz="UTC")

    def __init__(self, attributes: dict = None, **kwargs):
        super().__init__(attributes, **kwargs)
        self.connection = getattr(self.__class__, "__connection__", "default")
        self._global_scopes = {}
        self.__with__ = {}
        self._exists = False
        self._was_recently_created = False
        self._relationship = {}

    @property
    def __attributes__(self):
        return self.get_attributes()

    def is_loaded(self) -> bool:
        return self._exists

    def is_created(self) -> bool:
        """Returns True if this model has been persisted to the database."""
        return self._exists

    def all_attributes(self) -> dict:
        """Returns all model attributes (original + dirty)."""
        return self.get_attributes()

    def get_builder(self):
        return self.new_query()

    def add_relation(self, data: dict):
        self._relationship.update(data)

    @property
    def _relationships(self):
        """Alias for _relationship, used by relationship descriptors."""
        return self._relationship

    def get_related(self, key: str):
        return getattr(self.__class__, key)

    @classmethod
    def with_(cls, *eagers) -> "QueryBuilder":
        return cls.query().with_(*eagers)

    @classmethod
    def where(cls, column, *args) -> "QueryBuilder":
        return cls.query().where(column, *args)

    @classmethod
    def or_where(cls, column, *args) -> "QueryBuilder":
        return cls.query().or_where(column, *args)

    @classmethod
    def where_null(cls, column: str) -> "QueryBuilder":
        return cls.query().where_null(column)

    @classmethod
    def where_not_null(cls, column: str) -> "QueryBuilder":
        return cls.query().where_not_null(column)

    @classmethod
    def or_where_null(cls, column: str) -> "QueryBuilder":
        return cls.query().or_where_null(column)

    @classmethod
    def or_where_not_null(cls, column: str) -> "QueryBuilder":
        return cls.query().or_where_not_null(column)

    @classmethod
    def where_raw(cls, expression: str, bindings=()) -> "QueryBuilder":
        return cls.query().where_raw(expression, bindings)

    @classmethod
    def or_where_raw(cls, expression: str, bindings=()) -> "QueryBuilder":
        return cls.query().or_where_raw(expression, bindings)

    @classmethod
    def where_in(cls, column: str, values) -> "QueryBuilder":
        return cls.query().where_in(column, values)

    @classmethod
    def where_not_in(cls, column: str, values) -> "QueryBuilder":
        return cls.query().where_not_in(column, values)

    @classmethod
    def select(cls, *args) -> "QueryBuilder":
        return cls.query().select(*args)

    @classmethod
    def limit(cls, limit: int) -> "QueryBuilder":
        return cls.query().limit(limit)

    @classmethod
    def offset(cls, offset: int) -> "QueryBuilder":
        return cls.query().offset(offset)

    @classmethod
    def order_by(cls, column: str, direction: str = "asc") -> "QueryBuilder":
        return cls.query().order_by(column, direction)

    @classmethod
    def order_by_raw(cls, expression: str) -> "QueryBuilder":
        return cls.query().order_by_raw(expression)

    @classmethod
    def latest(cls, column: str = "created_at") -> "QueryBuilder":
        return cls.query().latest(column)

    @classmethod
    def oldest(cls, column: str = "created_at") -> "QueryBuilder":
        return cls.query().oldest(column)

    @classmethod
    def group_by(cls, column: str) -> "QueryBuilder":
        return cls.query().group_by(column)

    @classmethod
    def group_by_raw(cls, expression: str) -> "QueryBuilder":
        return cls.query().group_by_raw(expression)

    @classmethod
    def having(cls, column: str, equality: str, value) -> "QueryBuilder":
        return cls.query().having(column, equality, value)

    @classmethod
    def between(cls, column: str, low, high) -> "QueryBuilder":
        return cls.query().between(column, low, high)

    @classmethod
    def not_between(cls, column: str, low, high) -> "QueryBuilder":
        return cls.query().not_between(column, low, high)

    @classmethod
    def distinct(cls) -> "QueryBuilder":
        return cls.query().distinct()

    @classmethod
    def join(cls, table: str, column1: str, equality: str, column2: str, clause: str = "join") -> "QueryBuilder":
        return cls.query().join(table, column1, equality, column2, clause)

    @classmethod
    def left_join(cls, table: str, column1: str, equality: str, column2: str) -> "QueryBuilder":
        return cls.query().left_join(table, column1, equality, column2)

    @classmethod
    def right_join(cls, table: str, column1: str, equality: str, column2: str) -> "QueryBuilder":
        return cls.query().right_join(table, column1, equality, column2)

    @classmethod
    def where_column(cls, column1: str, column2: str) -> "QueryBuilder":
        return cls.query().where_column(column1, column2)

    @classmethod
    def when(cls, condition, callback) -> "QueryBuilder":
        return cls.query().when(condition, callback)

    @classmethod
    def where_exists(cls, builder: "QueryBuilder") -> "QueryBuilder":
        return cls.query().where_exists(builder)

    @classmethod
    def or_where_exists(cls, builder: "QueryBuilder") -> "QueryBuilder":
        return cls.query().or_where_exists(builder)

    @classmethod
    def where_has(cls, relation: str, callback=None) -> "QueryBuilder":
        return cls.query().where_has(relation, callback)

    @classmethod
    def or_where_has(cls, relation: str, callback=None) -> "QueryBuilder":
        return cls.query().or_where_has(relation, callback)

    @classmethod
    async def find(cls, primary_key: str | int, columns=None):
        return await cls.query().find(primary_key, columns)

    @classmethod
    async def find_or_fail(cls, primary_key: str | int, columns=None):
        return await cls.query().find_or_fail(primary_key, columns)

    @classmethod
    async def first_or_fail(cls, columns=None):
        return await cls.query().first_or_fail(columns)

    @classmethod
    async def first(cls, columns=None):
        return await cls.query().first(columns)

    @classmethod
    async def get(cls):
        return await cls.query().get()

    @classmethod
    def on(cls, connection: str):
        return cls().set_connection(connection)

    @classmethod
    async def all(cls):
        return await cls.query().get()

    @classmethod
    async def count(cls, column: str = "*"):
        return await cls.query().count(column)

    def set_connection(self, connection: str):
        self.connection = connection

        return self

    def get_connection_name(self):
        return self.connection

    def new_model_instance(self, attributes=None, exists=False):
        if attributes is None:
            attributes = {}
        model = self.__class__()
        model._attributes = attributes
        model._exists = exists

        return model

    def new_query(self):
        return self.db_manager.connection(self.connection).query().set_model(self)

    def hydrate(self, items):
        instance = self.new_model_instance()

        items = [instance.new_from_builder(item) for item in items]

        return instance.new_collection(items)

    def new_collection(self, models: list):
        collection = Collection(items=models)

        collection.with_relationship_autoloading()

        return collection

    def new_from_builder(self, attributes: dict, connection: str | None = None):
        model = self.new_model_instance([], exists=True)
        model.set_raw_attributes(attributes, True)

        model.set_connection(connection or self.get_connection_name())
        # Fire model event retrieved

        return model

    def __getattr__(self, attribute):
        return self.get_attribute(attribute)

    @classmethod
    def query(cls):
        return cls().new_query()

    @classmethod
    async def first_or_create(cls, search: dict, attributes: dict | None = None) -> "Model":
        return await cls.query().first_or_create(search, attributes)

    @classmethod
    async def update_or_create(cls, search: dict, attributes: dict | None = None) -> "Model":
        return await cls.query().update_or_create(search, attributes)

    @classmethod
    async def create(cls, attributes: dict):
        instance = cls().new_model_instance(attributes)
        await instance.save()

        return instance

    @classmethod
    async def insert(cls, values: dict | list) -> int | None:
        return await cls.query().insert(values)

    async def update(self, attributes: dict) -> bool:
        if not self._exists:
            return False

        return await self.fill(attributes).save()

    def fill(self, attributes: dict) -> "Model":
        for key, value in attributes.items():
            if key in self.__fillable__:
                self.set_attribute(key, value)
        return self

    async def save(self, options: dict | None = None):
        query = self.new_query()

        self.observe_events(self, "saving")

        if self._exists:
            saved = await self.perform_update(query) if self.is_dirty() else True
        else:
            saved = await self.perform_insert(query)

        if saved:
            self.finish_saving(options)

        return saved

    def finish_saving(self, options: dict | None = None):
        self.observe_events(self, "saved")
        self.sync_original()

    async def perform_insert(self, query) -> bool:
        attributes = self.get_attributes_for_insert()

        """if the model set auto incrementing, we need to set back the primary key to the inserted id."""
        if self.__incrementing__:
            inserted_id = await query.insert_get_id(attributes)
            self._attributes[self.__primary_key__] = inserted_id
            self._dirty_attributes[self.__primary_key__] = inserted_id

        else:
            await query.insert(attributes)

        self._exists = True
        self._was_recently_created = True
        self.observe_events(self, "created")
        return True

    async def perform_update(self, query) -> bool:
        dirty = self.get_dirty()
        if not dirty:
            return True

        pk_value = self.get_attribute(self.__primary_key__)
        await query.where(self.__primary_key__, pk_value).update(dirty)

        self.observe_events(self, "updated")
        return True

    def sync_original(self):
        self._attributes = self.get_attributes()
        self._dirty_attributes = {}
        self._original = dict(self._attributes)

    def get_attributes(self) -> dict:
        return {**self._attributes, **self._dirty_attributes}

    def serialize(self) -> dict:
        return self.get_attributes()

    @classmethod
    def where(cls, column, *args):
        return cls().query().where(column, *args)

    @classmethod
    def where_in(cls, column, values):
        return cls().query().where_in(column, values)

    def get_table_name(self):
        return self.__table__ or inflection.tableize(self.__class__.__name__)
