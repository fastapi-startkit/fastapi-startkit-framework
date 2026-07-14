from fastapi_startkit.masoniteorm.models.model import Model


class SeededUser(Model):
    """Real model backing the sqlite table the fixture seeders write into."""

    __table__ = "seed_users"
    __timestamps__ = False

    name: str
