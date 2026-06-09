from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

import inflection

try:
    from faker import Faker
except ImportError:  # pragma: no cover
    Faker = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.models import Model


class Factory(ABC):
    """
    Model factory base class.

    Subclass, set ``model``, implement ``definition()``, and optionally
    override ``configure()`` to wire lifecycle hooks.

    Usage::

        class UserFactory(Factory):
            model = User

            def definition(self) -> dict:
                return {
                    "name": self.fake.name(),
                    "email": self.fake.email(),
                }

        user  = await UserFactory.new().create()
        users = await UserFactory.new().count(5).create()
    """

    model: "type[Model]"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        if Faker is None:  # pragma: no cover
            raise ImportError("The 'faker' package is required to use Factory. Install it with: pip install faker")
        self.fake: Faker = Faker()
        self._count: int = 1
        self._state_callbacks: list[Callable] = []
        self._after_making_callbacks: list[Callable] = []
        self._after_creating_callbacks: list[Callable] = []
        self._has_factories: list[Factory] = []
        self._for_factories: list[Factory] = []

    @classmethod
    def new(cls) -> "Factory":
        """
        Create a fresh factory instance. Calls ``configure()`` automatically
        if it is defined on the subclass.
        """
        instance = cls()
        # Call configure() only when the subclass overrides it
        if type(instance).configure is not Factory.configure:
            instance.configure()
        return instance

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------

    @abstractmethod
    def definition(self) -> dict:
        """Return the default attribute map for a new model instance."""
        ...

    # ------------------------------------------------------------------
    # Lifecycle hook registration
    # ------------------------------------------------------------------

    def configure(self) -> "Factory":
        """
        Override in a subclass to register lifecycle callbacks::

            def configure(self):
                return self.after_making(cb).after_creating(cb)
        """
        return self

    def after_making(self, callback: Callable) -> "Factory":
        """Register a callback invoked after each ``make()`` call."""
        self._after_making_callbacks.append(callback)
        return self

    def after_creating(self, callback: Callable) -> "Factory":
        """Register a callback invoked after each ``create()`` call."""
        self._after_creating_callbacks.append(callback)
        return self

    # ------------------------------------------------------------------
    # Fluent chainable helpers
    # ------------------------------------------------------------------

    def count(self, n: int) -> "Factory":
        """Produce *n* instances on the next ``create()`` / ``make()`` call."""
        self._count = n
        return self

    def state(self, callback: Callable[[dict], dict]) -> "Factory":
        """
        Register a state callback.  Called with the current attrs dict and
        must return a dict of partial overrides to merge in.

        Typically used from a named state method::

            class UserFactory(Factory):
                def suspended(self):
                    return self.state(lambda attrs: {"account_status": "suspended"})
        """
        self._state_callbacks.append(callback)
        return self

    def has(self, other_factory: "Factory") -> "Factory":
        """
        After ``create()``, persist records from *other_factory* and inject
        this model's primary key as a foreign key into those records.

        The foreign key is inferred as ``{parent_table_singular}_id``.
        """
        self._has_factories.append(other_factory)
        return self

    def for_(self, other_factory: "Factory") -> "Factory":
        """
        Before ``create()``, persist *other_factory* and inject its primary
        key as a foreign key into this model's attributes.

        The foreign key is inferred as ``{parent_table_singular}_id``.
        """
        self._for_factories.append(other_factory)
        return self

    # ------------------------------------------------------------------
    # Attribute building helpers
    # ------------------------------------------------------------------

    def _build_attributes(self, overrides: dict) -> dict:
        """Merge definition + state callbacks + caller overrides."""
        attrs = self.definition()
        for cb in self._state_callbacks:
            attrs.update(cb(attrs))
        attrs.update(overrides)
        return attrs

    @staticmethod
    def _infer_fk(model_cls: "type[Model]") -> str:
        """Return the inferred foreign-key column name for *model_cls*."""
        table = getattr(model_cls, "__table__", None) or inflection.tableize(model_cls.__name__)
        singular = inflection.singularize(table)
        return f"{singular}_id"

    @staticmethod
    async def _invoke(callback: Callable, instance: "Model") -> None:
        """Call *callback* with *instance*, awaiting if it is a coroutine."""
        result = callback(instance)
        if inspect.isawaitable(result):
            await result

    # ------------------------------------------------------------------
    # Core factory methods
    # ------------------------------------------------------------------

    async def make(self, **overrides) -> "Model | list[Model]":
        """
        Build model instance(s) **in memory** without persisting to the DB.

        Returns a single instance when no ``.count()`` was set, or a list
        when ``.count(n)`` was called.
        """
        model_cls = self.model
        single = self._count == 1
        count = self._count

        results: list[Model] = []
        for _ in range(count):
            attrs = self._build_attributes(overrides)
            instance = model_cls(attrs)
            for cb in self._after_making_callbacks:
                await self._invoke(cb, instance)
            results.append(instance)

        return results[0] if single else results

    async def create(self, **overrides) -> "Model | list[Model]":
        """
        Persist model instance(s) to the database.

        Returns a single instance when no ``.count()`` was set, or a list
        when ``.count(n)`` was called.
        """
        # ---- Handle parent (for_) relationships ----
        for parent_factory in self._for_factories:
            parent = await parent_factory.create()
            fk = self._infer_fk(parent_factory.model)
            pk_val = parent.get_attribute(parent_factory.model.__primary_key__)
            overrides.setdefault(fk, pk_val)

        model_cls = self.model
        single = self._count == 1
        count = self._count

        results: list[Model] = []
        for _ in range(count):
            attrs = self._build_attributes(overrides)
            instance = await model_cls.create(attrs)

            # ---- Handle child (has) relationships ----
            for child_factory in self._has_factories:
                parent_fk = self._infer_fk(model_cls)
                pk_val = instance.get_attribute(model_cls.__primary_key__)
                await child_factory.create(**{parent_fk: pk_val})

            for cb in self._after_creating_callbacks:
                await self._invoke(cb, instance)

            results.append(instance)

        return results[0] if single else results
