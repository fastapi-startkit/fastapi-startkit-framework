class Channel:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Channel):
            return NotImplemented
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class PrivateChannel(Channel):
    def __init__(self, name: str):
        super().__init__(f"private-{name}")


class PresenceChannel(Channel):
    def __init__(self, name: str):
        super().__init__(f"presence-{name}")
