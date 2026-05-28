from fastapi_startkit.masoniteorm.seeds import Seeder
from app.models.Account import Account
from app.models.User import User
from app.models.Organization import Organization
from app.models.Contact import Contact
from databases.factories.UserFactory import UserFactory
from databases.factories.OrganizationFactory import OrganizationFactory
from databases.factories.ContactFactory import ContactFactory
import random


class DatabaseSeeder(Seeder):
    async def run(self):
        """Run the database seeds."""
        # Create Account
        account = await Account.create({"name": "Acme Corporation"})

        # Create User
        await User.first_or_create(
            {
                "email": "johndoe@example.com",
            },
            {
                "account_id": account.id,
                "first_name": "John",
                "last_name": "Doe",
                "password": "secret",  # TODO: Use hash
                "owner": True,
            },
        )

        # Create 5 more users
        await UserFactory.new().count(5).create(account_id=account.id)

        # Create 100 organizations
        organizations = (
            await OrganizationFactory.new().count(100).create(account_id=account.id)
        )

        # Create 100 contacts
        for _ in range(100):
            await ContactFactory.new().create(
                account_id=account.id, organization_id=random.choice(organizations).id
            )
