from faker import Faker
from fastapi_startkit.masoniteorm.factory import Factory
from app.models.User import User

fake = Faker()


class UserFactory(Factory):
    model = User

    def definition(self):
        return {
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.unique.email(),
            "password": "secret",
            "owner": False,
            "photo_path": None,
        }

    def configure(self):
        async def making(user):
            print(f"Making user: {user.name}")

        async def created(user):
            print(f"Created user: {user.name}")

        return self.after_making(making).after_creating(created)

    def suspended(self):
        return self.state(
            lambda attributes: {
                "account_status": "suspended",
            }
        )
