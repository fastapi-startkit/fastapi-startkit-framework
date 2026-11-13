# 082 — Notification broadcast channel, read state and generator

- Date: 2026-11-13
- Status: Accepted

## Problem

ADR 064 added `fastapi_startkit.notifications` with `mail` and `database` channels, `Notifiable.notify()` and `Notifiable.notifications()`. Compared with Laravel's notifications, applications still miss:

- A `broadcast` channel. The `broadcasting` package (Reverb and log drivers, `BroadcastManager.emit`) exists, but a notification cannot reach a browser in real time, and Laravel Echo's `.notification()` listener receives nothing.
- Read state. The `read_at` column is written but nothing reads or updates it, so "unread badge" and "mark all as read" have to be hand-written SQL.
- `Notification.send_now()`. Laravel apps call it to bypass queues; the facade has no such method.
- A generator. Every other scaffolded class (`db:make:model`, `db:make:observer`) has a command; notifications do not.

## Alternatives

Broadcast transport:

- **Wrap each notification in a `BroadcastEvent` subclass.** Reuses `BroadcastManager.dispatch`, but needs a dynamic class per notification for `broadcast_on`/`broadcast_as`/`broadcast_with`. Rejected as indirect.
- **Call `BroadcastManager.emit(channel, event, payload)` per channel.** Already the escape hatch for dynamic broadcasts, honours the configured driver. Chosen.

Event name:

- **Our own name (`notification.created`).** Echo's `.notification()` helper would not match it. Rejected.
- **`Illuminate\Notifications\Events\BroadcastNotificationCreated`.** The name Laravel Echo listens for, so `Echo.private(...).notification(cb)` works unchanged against Reverb. Chosen; a notification may override `broadcast_as()`.

Read state API:

- **A `DatabaseNotification` ORM model with `mark_as_read()`.** Closest to Laravel, but the table name and connection come from config at runtime while `Model` binds them at class level, and `notifications()` already returns plain rows. Rejected for now.
- **Query helpers on `DatabaseChannel`, exposed through `Notifiable`.** Keeps rows as dicts, honours the configured table and connection. Chosen.

Queueing: there is no queue package (only a stale `Queue` facade stub), so `send_now` is an alias of `send` and queued notifications stay deferred.

## Decision

- `BroadcastChannel(broadcasting)` in `notifications/channels.py`. It renders `to_broadcast(notifiable)`, falling back to `to_array`. The payload is that dict plus `id` (the notification id) and `type` (`notification.broadcast_type()`, default class name). It resolves the route with `notifiable.route_notification_for("broadcast", notification)`; when that returns the notifiable itself it uses `notifiable.receives_broadcast_notifications_on()`, which `Notifiable` implements as `"{notifiable_type}.{notifiable_key}"`. A route may be a string, a `broadcasting.Channel` or a list of either; strings become `PrivateChannel`, matching Laravel. An empty route skips the channel. Each channel name is sent with `await broadcasting.emit(name, notification.broadcast_as(), payload)`.
- `Notification` gains `broadcast_as()` (default `Illuminate\Notifications\Events\BroadcastNotificationCreated`) and `broadcast_type()` (default class name).
- `DatabaseChannel` gains `notifications_for(notifiable, read=None)` (`True` read only, `False` unread only), `mark_as_read(notifiable, ids=None)` and `mark_as_unread(notifiable, ids=None)`; `ids=None` targets all of the notifiable's rows; both return the updated row count. `mark_as_read` only touches rows whose `read_at` is NULL, so the first read time is kept.
- `Notifiable` gains `unread_notifications()`, `read_notifications()`, `mark_notifications_as_read(*ids)` and `mark_notifications_as_unread(*ids)`.
- `ChannelManager.send_now` is an alias of `send`.
- `NotificationProvider` registers the `broadcast` channel, resolving `broadcasting` lazily with the same "requires ReverbProvider" error as mail and database, and registers `MakeNotificationCommand` (`make:notification Name [-d app/notifications]`), which renders a stub with `via`, `to_mail` and `to_array` into `app/notifications/<snake_name>.py` and refuses to overwrite.
- `Notification.pyi` adds `send_now`.

No core abstraction changes; the work is additive.

## Validation

- Tests in `tests/notifications/`: broadcast payload and default private channel for a model, string, `Channel` and list routes, anonymous routes, `broadcast_as` override, missing route skips, missing `ReverbProvider` error; read/unread filters, `mark_notifications_as_read` with and without ids keeps the first `read_at`, `mark_notifications_as_unread`; a notification with `mail`, `database` and `broadcast` in `via()` reaching all three; `send_now`; `make:notification` output and the no-overwrite path.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov` passes and stays above `fail_under`.
