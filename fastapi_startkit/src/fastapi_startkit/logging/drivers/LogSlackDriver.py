from .BaseDriver import BaseDriver
import requests


class SlackApiError(Exception):
    pass


class SlackChannelNotFound(SlackApiError):
    pass


class LogSlackDriver(BaseDriver):
    def __init__(self, *args, **kwargs):
        self.slack_url = "https://slack.com/api/chat.postMessage"
        self.token = kwargs.get("token")
        self.channel = kwargs.get("channel")
        self.emoji = kwargs.get("emoji", ":warning:")
        self.username = kwargs.get("username")

    def emergency(self, message, *args, **kwargs):
        self.send(self.get_format(message, "EMERGENCY"))

    def alert(self, message, *args, **kwargs):
        self.send(self.get_format(message, "ALERT"))

    def critical(self, message, *args, **kwargs):
        self.send(self.get_format(message, "CRITICAL"))

    def error(self, message, *args, **kwargs):
        self.send(self.get_format(message, "ERROR"))

    def warning(self, message, *args, **kwargs):
        self.send(self.get_format(message, "WARNING"))

    def notice(self, message, *args, **kwargs):
        self.send(self.get_format(message, "NOTICE"))

    def info(self, message, *args, **kwargs):
        self.send(self.get_format(message, "INFO"))

    def debug(self, message, *args, **kwargs):
        self.send(self.get_format(message, "DEBUG"))

    def get_format(self, message, level):
        return "{time} - {level} - {message}".format(
            time=self.get_time().to_datetime_string(), message=message, level=level
        )

    def send(self, message):
        payload = {
            "channel": self.channel,
            "text": message,
            "username": self.username,
            "icon_emoji": self.emoji,
        }
        response = requests.post(
            self.slack_url,
            json={key: value for key, value in payload.items() if value is not None},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("ok"):
            return

        error = body.get("error", "unknown_error")
        exception = SlackChannelNotFound if error == "channel_not_found" else SlackApiError
        raise exception(f"Slack chat.postMessage failed for channel {self.channel!r}: {error}")
