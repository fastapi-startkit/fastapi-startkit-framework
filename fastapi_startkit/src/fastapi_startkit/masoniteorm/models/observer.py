class CreatedAtObserver:
    def __init__(self, field_name: str, fmt: str | None, tz: str):
        self.field_name = field_name
        self.fmt = fmt
        self.tz = tz


class UpdatedAtObserver:
    def __init__(self, field_name: str, fmt: str | None, tz: str):
        self.field_name = field_name
        self.fmt = fmt or "YYYY-MM-DD HH:mm:ss"
        self.tz = tz
