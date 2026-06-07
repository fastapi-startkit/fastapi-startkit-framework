class Channel:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"


class PrivateChannel(Channel):
    def __init__(self, name: str):
        super().__init__(f"private-{name}")


class PresenceChannel(Channel):
    def __init__(self, name: str):
        super().__init__(f"presence-{name}")
