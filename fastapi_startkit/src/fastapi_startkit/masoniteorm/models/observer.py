import pendulum


class CreatedAtObserver:
    def __init__(self, field_name: str, fmt: str | None, tz: str):
        self.field_name = field_name
        self.fmt = fmt
        self.tz = tz

    def creating(self, model):
        if model.__timestamps__ and model.get_attributes().get(self.field_name) is None:
            setattr(model, self.field_name, pendulum.now(self.tz))


class UpdatedAtObserver:
    def __init__(self, field_name: str, fmt: str | None, tz: str):
        self.field_name = field_name
        self.fmt = fmt or "YYYY-MM-DD HH:mm:ss"
        self.tz = tz

    def creating(self, model):
        if model.__timestamps__ and model.get_attributes().get(self.field_name) is None:
            setattr(model, self.field_name, pendulum.now(self.tz))

    def updating(self, model):
        if model.__timestamps__ and self.field_name not in model.get_dirty():
            setattr(model, self.field_name, pendulum.now(self.tz))
