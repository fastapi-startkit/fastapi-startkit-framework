# 064 — Mail and notifications

- Date: 2026-11-06
- Status: Accepted

## Problem

`facades/Mail.py` and `facades/Notification.py` exist and resolve the `mail` and `notification` container keys, but nothing binds those keys, so every call fails. Their `.pyi` stubs describe a Masonite-style API (`add_driver`, `set_configuration`, `mailable(...).send(driver)`) that was never implemented. `NotificationException` exists and is unused. Applications that need to send a welcome email or record an in-app notification have to call `smtplib` by hand, with no shared config, no way to keep mail out of tests and no place to describe "this event reaches the user by mail and in the database".

Laravel solves this with two layers: `Mailable` + `Mail` (mailers configured in `config/mail.php`) and `Notification` + `Notifiable` (a notification lists its channels in `via()` and renders itself per channel with `toMail()`, `toDatabase()`). The framework already follows Laravel's provider/config/facade layout (cache, broadcasting, redis), so applications expect the same here.

## Alternatives

Mail transport:

- **`aiosmtplib`.** Native async SMTP, but a new dependency, and the lock file must not change in this task. Rejected for now; it can be added later as another driver through `MailManager.extend`.
- **`fastapi-mail`.** Brings its own config model and pydantic settings, and does not fit the provider/config/facade pattern. Rejected.
- **Stdlib `smtplib` run through `asyncio.to_thread`.** No dependency, supports STARTTLS and implicit TLS, keeps the public API awaitable. Chosen.

Message model:

- **Expose `email.message.EmailMessage` directly.** Low level; no recipient defaults, no `build()` hook for reusable mail classes. Rejected as the public API, kept as the transport format.
- **Fluent `Mailable` with a `build()` hook that compiles to `EmailMessage`.** Mirrors Laravel's `Mailable`, works inline (`Mailable().to(...).subject(...)`) and as a subclass. Chosen.

Notifications:

- **Event listeners per channel.** Every app re-implements channel routing and storage. Rejected.
- **`Notification.via()` returning channel names, rendered by `to_<channel>()`, sent through a channel manager.** Mirrors Laravel, lets apps add channels with `extend`. Chosen.

Masonite-style stub API: replaced. It was never implemented, so no code depends on it.

## Decision

New package `fastapi_startkit.mail`:

- `MailConfig` (`default` from `MAIL_MAILER`, default `log`; `from_address`/`from_name` from `MAIL_FROM_ADDRESS`/`MAIL_FROM_NAME`; `mailers` with `smtp`, `log` and `array`). `SmtpMailerConfig` reads `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_ENCRYPTION` (`tls` for STARTTLS, `ssl` for implicit TLS, empty for none) and `MAIL_TIMEOUT`.
- `Mailable`: `to`, `cc`, `bcc`, `reply_to`, `from_`, `subject`, `html`, `text`, `attach(path, name, mime)`, `attach_data(data, name, mime)`, each returning `self`; `has_to()`; `build()` is a no-op hook subclasses override; `to_message(default_from)` runs `build()` once and returns an `EmailMessage` (text part, HTML alternative, attachments). Addresses are strings or `(address, name)` tuples; any object with an `email` attribute (a user model) is accepted too. Missing recipients or subject raise `ValueError`.
- Transports implement `async send(message: EmailMessage)`: `SmtpTransport` (stdlib `smtplib` via `asyncio.to_thread`), `LogTransport` (writes a readable summary — headers, text or HTML body, attachment names — to the `fastapi_startkit.mail` logger, or the logger named by the mailer's `channel`) and `ArrayTransport` (keeps messages in `messages` for tests).
- `Mailer(name, transport, from)` with `async send(mailable)` returning the sent `EmailMessage`. `MailManager` caches mailers by name, `mailer(name)` resolves one from config, `extend(driver, factory)` adds drivers, `to(*addresses)` returns a `PendingMail` (`await Mail.to(user).send(WelcomeMail())`), and unknown attributes proxy to the default mailer, so `await Mail.send(mailable)` works.
- `MailProvider` (`provider_key = "mail"`) merges `MailConfig` into `config("mail")`, binds `mail` and publishes `config/mail.py`.

New package `fastapi_startkit.notifications`:

- `Notification`: `via(notifiable) -> list[str]` (default `[]`), `to_<channel>(notifiable)` per channel, `to_array` as the database fallback, and an `id` (uuid4 hex) assigned at send time.
- `MailMessage(Mailable)`: `greeting`, `line`, `action(text, url)`, `salutation`; renders text and HTML from the lines when no body was set.
- `Notifiable` mixin: `await user.notify(notification)`; `route_notification_for(channel, notification)` calls `route_notification_for_<channel>` when defined, else returns `email` for `mail` and `self` for other channels; `await notifications()` returns this notifiable's rows from the notifications table, newest first. `notifiable_type` is the morph name for models (class name otherwise) and `notifiable_id` the primary key, stored as a string so integer and uuid keys share one column.
- `AnonymousNotifiable` via `Notification.route("mail", "a@b.c").notify(n)`.
- Channels implement `async send(notifiable, notification)`. `MailChannel` calls `to_mail`, accepts a `Mailable` (including `MailMessage`), fills `to` from the route when the mailable has none and sends through the mailer named by `notification.mailer` (default mailer otherwise). `DatabaseChannel` inserts `id`, `type` (class name), `notifiable_type`, `notifiable_id`, `data` (JSON of `to_database` or `to_array`), `read_at` (NULL) and timestamps.
- `ChannelManager.send(notifiables, notification)` takes one notifiable or a list, sends to each channel from `via()`; unknown channels raise `NotificationException`. `extend(name, factory)` adds channels.
- `NotificationConfig` (`table` from `NOTIFICATIONS_TABLE`, default `notifications`; `connection` from `DB_NOTIFICATIONS_CONNECTION`). `NotificationProvider` binds `notification`, resolves `mail` and `db` lazily (so database-only or mail-only apps work), and publishes `config/notifications.py` and the `create_notifications_table` migration.

Facade stubs (`Mail.pyi`, `Notification.pyi`) describe the new API. No core abstraction changes; the work is additive.

Queued mail and notifications, Markdown/Jinja templates, a `Mail.fake()`/`Notification.fake()` recorder and broadcast channels are deferred.

## Validation

- Unit tests under `tests/mail/` and `tests/notifications/`: builder output (headers, parts, attachments, address forms), validation errors, `build()` hook, the array, log (via `assertLogs`) and SMTP drivers (with `smtplib.SMTP`/`SMTP_SSL` mocked: STARTTLS, login, `send_message`), manager resolution, `extend`, `PendingMail`, provider config defaults with no env set.
- Notifications: `via()` routing, `MailMessage` rendering, mail channel recipient fill-in, database channel rows in in-memory SQLite created by the published migration, `notify()` on a model reaching both channels, anonymous notifiables, unknown-channel errors.
- `uv run pytest --cov` stays above `fail_under`.
