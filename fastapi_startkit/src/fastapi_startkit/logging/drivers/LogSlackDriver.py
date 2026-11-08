import sys
import time

import requests

from .BaseDriver import BaseDriver


class SlackApiError(Exception):
    pass


class SlackChannelNotFound(SlackApiError):
    pass


class LogSlackDriver(BaseDriver):
    default_retry_after = 30.0

    def __init__(self, *args, **kwargs):
        self.slack_url = "https://slack.com/api/chat.postMessage"
        self.token = kwargs.get("token")
        self.channel = kwargs.get("channel")
        self.emoji = kwargs.get("emoji", ":warning:")
        self.username = kwargs.get("username")
        self.rate_limited_until = 0.0

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
        if not self.token:
            self.warn("token is not configured, message skipped")
            return

        if time.monotonic() < self.rate_limited_until:
            self.warn("rate limited by Slack, message skipped")
            return

        try:
            self.post(message)
        except (requests.RequestException, ValueError, SlackApiError) as error:
            self.warn(error)

    def post(self, message):
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
        if response.status_code == 429:
            self.rate_limited_until = time.monotonic() + self.retry_after(response)

        response.raise_for_status()
        body = response.json()
        if body.get("ok"):
            return

        error = body.get("error", "unknown_error")
        exception = SlackChannelNotFound if error == "channel_not_found" else SlackApiError
        raise exception(f"Slack chat.postMessage failed for channel {self.channel!r}: {error}")

    def retry_after(self, response):
        try:
            return float(response.headers.get("Retry-After", self.default_retry_after))
        except ValueError:
            return self.default_retry_after

    def warn(self, reason):
        print(f"Slack log driver: {reason}", file=sys.stderr)
