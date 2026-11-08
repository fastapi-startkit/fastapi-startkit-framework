from fastapi_startkit.application import app
from fastapi_startkit.masoniteorm.models.caster import BaseCast


def hash_password(password: str) -> str:
    return app().make("auth_manager").hasher.make(password)


def is_hashed(value: str) -> bool:
    return value.startswith(("$2a$", "$2b$", "$2y$")) and len(value) == 60


class Hashed(BaseCast):
    def set(self, value):
        return value if value is None or is_hashed(value) else hash_password(value)
