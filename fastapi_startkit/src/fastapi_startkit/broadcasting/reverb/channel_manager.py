class ChannelManager:
    def __init__(self):
        self._subscriptions: dict[str, set[str]] = {}

    def subscribe(self, channel: str, socket_id: str) -> None:
        self._subscriptions.setdefault(channel, set()).add(socket_id)

    def unsubscribe(self, channel: str, socket_id: str) -> None:
        subscribers = self._subscriptions.get(channel)
        if subscribers is None:
            return
        subscribers.discard(socket_id)
        if not subscribers:
            del self._subscriptions[channel]

    def remove_socket(self, socket_id: str) -> None:
        for channel in list(self._subscriptions):
            self.unsubscribe(channel, socket_id)

    def subscribers(self, channel: str) -> set[str]:
        return set(self._subscriptions.get(channel, set()))
