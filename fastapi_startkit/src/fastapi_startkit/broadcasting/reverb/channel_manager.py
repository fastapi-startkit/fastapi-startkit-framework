class ChannelManager:
    def __init__(self):
        self._subscriptions: dict[str, set] = {}

    def subscribe(self, channel: str, socket_id: str) -> None:
        self._subscriptions.setdefault(channel, set()).add(socket_id)

    def unsubscribe(self, channel: str, socket_id: str) -> None:
        if channel in self._subscriptions:
            self._subscriptions[channel].discard(socket_id)

    def remove_socket(self, socket_id: str) -> None:
        for subs in self._subscriptions.values():
            subs.discard(socket_id)

    def subscribers(self, channel: str) -> set:
        return set(self._subscriptions.get(channel, set()))
