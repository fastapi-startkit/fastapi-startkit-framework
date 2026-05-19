class Registry:
    _models: dict[str, type] = {}
    _morph_map: dict[str, type] = {}
    _reverse_map: dict[type, str] = {}

    @classmethod
    def register(cls, model: type):
        name = model.__name__
        morph_name = model.get_morph_class() if hasattr(model, "get_morph_class") else name

        cls._models[name] = model

        # priority is given to morph_name for resolution
        if morph_name not in cls._morph_map:
            cls._morph_map[morph_name] = model
            cls._reverse_map[model] = morph_name

        return model

    @classmethod
    def morph_map(cls, mapping: dict[str, type]):
        for alias, model in mapping.items():
            cls._morph_map[alias] = model
            cls._reverse_map[model] = alias  # override reverse lookup

    @classmethod
    def get_morph_map(cls) -> dict[str, type]:
        return cls._morph_map

    @classmethod
    def resolve(cls, name: str) -> type:
        # priority: class registry > morph_map
        # _models is always updated with the latest registration, so it wins over
        # _morph_map which only keeps the first-registered class per name.
        # _morph_map is still used for explicit morph aliases (e.g. "user", "article").
        if name in cls._models:
            return cls._models[name]

        if name in cls._morph_map:
            return cls._morph_map[name]

        raise ValueError(f"Model '{name}' not found in registry.")

    @classmethod
    def get_morph_name(cls, model: type) -> str:
        return cls._reverse_map.get(model, model.__name__)
