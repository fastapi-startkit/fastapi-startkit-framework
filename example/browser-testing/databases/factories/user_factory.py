from app.models.user import User
from fastapi_startkit.masoniteorm.factory import Factory


class UserFactory(Factory):
    model = User

    def definition(self):
        return {
            "name": self.fake.name(),
            "email": self.fake.unique.email(),
            "password": "password",
        }
