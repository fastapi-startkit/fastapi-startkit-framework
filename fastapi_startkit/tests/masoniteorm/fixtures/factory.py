from fastapi_startkit.orm.factory.factory import Factory
from .model import User


class UserFactory(Factory):
    model = User

    def definition(self) -> dict:
        return {"name": "Alex", "email": "tmgbedu@gmail.com"}
