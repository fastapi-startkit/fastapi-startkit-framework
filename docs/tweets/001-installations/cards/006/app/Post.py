from fastapi_startkit.masoniteorm.models import Model


class Post(Model):
    id: int
    title: str
    body: str
