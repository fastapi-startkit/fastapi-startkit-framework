from fastapi_startkit.masoniteorm.models import registry


class BaseRelationship:
    def __init__(self, fn: str | list[str], local_key=None, foreign_key=None):
        if not isinstance(fn, str):
            raise TypeError(f"Relationship {self.__class__.__name__} expects a string as the first argument")
        fn_str: str = fn  # For type checking
        self.fn = lambda: registry.Registry.resolve(fn_str)

        self.local_key = local_key
        self.foreign_key = foreign_key
        self.attribute = None

    def __set_name__(self, cls, name):
        self.attribute = name
        self.owner_class = cls

    def get_builder(self):
        return self.fn()().get_builder()

    def __get__(self, instance, owner):
        """
        This method is called when the decorated method is accessed.

        Arguments:
            instance {object|None} -- The instance we called.
                If we didn't call the attribute and only accessed it then this will be None.

            owner {object} -- The current model that the property was accessed on.

        Returns:
            object -- Either returns a builder or a hydrated model.
        """
        if instance is None:
            return self

        self.set_keys(instance, self.attribute)

        if not instance.is_loaded():
            return self

        if self.attribute in instance._relationships:
            return instance._relationships[self.attribute]

        return self.apply_query(self.get_builder(), instance)

    def __getattr__(self, attribute):
        return getattr(self.get_builder(), attribute)

    def apply_query(self, foreign, owner):
        """Return a dictionary to hydrate the model with

        Arguments:
            foreign {oject} -- The relationship object
            owner {object} -- The current model oject.

        Returns:
            dict -- A dictionary of data which will be hydrated.
        """
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'apply_query' method")

    def query_where_exists(self, builder, callback, method="where_exists"):
        """Adds a criteria clause to the query filter for existing related records"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'query_where_exists' method")

    def joins(self, builder, clause=None):
        """Helper method for adding join clauses to a relationship"""
        other_table = self.get_builder().get_table_name()
        local_table = builder.get_table_name()
        return builder.join(
            other_table,
            f"{local_table}.{self.local_key}",
            "=",
            f"{other_table}.{self.foreign_key}",
            clause=clause,
        )

    def get_with_count_query(self, builder, callback):
        """Add a correlated ``{attribute}_count`` column to ``builder``.

        Default implementation for direct relationships (HasMany/HasOne/
        BelongsTo): counts related rows whose foreign key matches the owner's
        local key. Through/pivot relationships override this.
        """
        related = self.get_builder()
        related_table = related.get_table_name()

        subquery = related.select_count("*").where_column(
            f"{related_table}.{self.foreign_key}",
            f"{builder.get_table_name()}.{self.local_key}",
        )
        if callback:
            callback(subquery)

        if not builder._columns:
            builder.select(f"{builder.get_table_name()}.*")
        return builder.select_sub(subquery, f"{self.attribute}_count")

    def attach(self, current_model, related_record):
        """Link a related model to the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'attach' method")

    def get_related(self, query, relation, eagers=None, callback=None):
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'get_related' method")

    def relate(self, related_record):
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'relate' method")

    def detach(self, current_model, related_record):
        """Unlink a related model from the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'detach' method")

    def attach_related(self, current_model, related_record):
        """Unlink a related model from the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'attach_related' method")

    def detach_related(self, current_model, related_record):
        """Unlink a related model from the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'detach_related' method")

    def query_has(self, current_query_builder, method="where_exists"):
        """Adds a clause to the query to check if a relation exists"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'query_has' method")

    def map_related(self, related_result):
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'map_related' method")
