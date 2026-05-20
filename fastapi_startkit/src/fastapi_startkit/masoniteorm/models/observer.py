import pendulum
from fastapi_startkit.masoniteorm.expressions.expressions import UpdateQueryExpression


class CreatedAtObserver:
    def __init__(self, field_name: str, fmt: str | None, tz: str):
        self.field_name = field_name
        self.fmt = fmt
        self.tz = tz

    def creating(self, model):
        if model.__timestamps__:
            setattr(model, self.field_name, pendulum.now(self.tz))


class UpdatedAtObserver:
    def __init__(self, field_name: str, fmt: str | None, tz: str):
        self.field_name = field_name
        self.fmt = fmt or "YYYY-MM-DD HH:mm:ss"
        self.tz = tz

    def creating(self, model):
        if model.__timestamps__:
            setattr(model, self.field_name, pendulum.now(self.tz))

    def updating(self, model):
        if model.__timestamps__:
            model.builder._updates += (UpdateQueryExpression({self.field_name: pendulum.now(self.tz)}),)
