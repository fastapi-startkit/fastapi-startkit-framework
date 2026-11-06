from dataclasses import dataclass, field

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class SmtpMailerConfig(Config):
    driver: str = "smtp"
    host: str = env("MAIL_HOST", "127.0.0.1")
    port: int = env("MAIL_PORT", 587)
    username: str | None = env("MAIL_USERNAME", None, cast=False)
    password: str | None = env("MAIL_PASSWORD", None, cast=False)
    encryption: str | None = env("MAIL_ENCRYPTION", "tls", cast=False)
    timeout: int = env("MAIL_TIMEOUT", 30)


@dataclass
class LogMailerConfig(Config):
    driver: str = "log"
    channel: str | None = env("MAIL_LOG_CHANNEL", None, cast=False)


@dataclass
class ArrayMailerConfig(Config):
    driver: str = "array"


@dataclass
class MailConfig(Config):
    default: str = env("MAIL_MAILER", "log")
    from_address: str = env("MAIL_FROM_ADDRESS", "hello@example.com")
    from_name: str = env("MAIL_FROM_NAME", "Example")
    mailers: dict[str, Config] = field(
        default_factory=lambda: {
            "smtp": SmtpMailerConfig(),
            "log": LogMailerConfig(),
            "array": ArrayMailerConfig(),
        }
    )


__all__ = ["ArrayMailerConfig", "LogMailerConfig", "MailConfig", "SmtpMailerConfig"]
