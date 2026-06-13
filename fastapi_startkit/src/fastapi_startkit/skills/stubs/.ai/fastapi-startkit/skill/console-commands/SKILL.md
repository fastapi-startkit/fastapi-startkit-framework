---
name: console-commands
description: Build artisan CLI commands with Cleo in fastapi-startkit. Use when adding new artisan commands, defining arguments/options, accessing the service container, or registering commands via a provider.
---

# Console Commands

Artisan commands are built on [Cleo](https://github.com/python-poetry/cleo). Each command is a class with a `name`, `description`, optional `arguments`/`options`, and a `handle()` method.

## Defining a command

```python
from cleo.helpers import argument, option
from fastapi_startkit.console import Command

class GreetCommand(Command):
    name = "greet"
    description = "Greet a user by name."

    arguments = [
        argument("username", description="The name to greet"),
    ]
    options = [
        option("shout", "s", description="Output in uppercase", flag=True),
    ]

    def handle(self):
        name = self.argument("username")
        msg = f"Hello, {name}!"
        if self.option("shout"):
            msg = msg.upper()
        self.line(msg)
```

Run it:

```bash
uv run artisan greet Alice
uv run artisan greet Alice --shout
```

## Async commands

For commands that call `async` framework code (e.g. ORM queries), wrap with `asyncio.run`:

```python
import asyncio
from fastapi_startkit.console import Command

class SyncUsersCommand(Command):
    name = "users:sync"
    description = "Synchronise users from the remote API."

    def handle(self):
        asyncio.run(self.handle_async())

    async def handle_async(self):
        from app.models import User
        users = await User.where("synced", False).get()
        self.line(f"Syncing {len(users)} users…")
```

## Accessing the container

`Command` carries a `container` property set by the framework before `handle()` is called. Resolve any bound service:

```python
def handle(self):
    config = self.container.make("config")
    db = self.container.make("db")
    self.line(config.get("app.name"))
```

## Output helpers

| Method | Description |
|--------|-------------|
| `self.line(msg)` | Print a line |
| `self.info(msg)` | Print in green |
| `self.comment(msg)` | Print in yellow |
| `self.error(msg)` | Print in red |
| `self.question(msg)` | Print in cyan |
| `self.line_error(msg)` | Print to stderr |
| `self.ask(question)` | Prompt for text input |
| `self.confirm(question)` | Prompt for yes/no |

## Registering commands in a provider

Expose commands from a service provider's `boot()` method:

```python
from fastapi_startkit.providers import Provider
from app.commands import GreetCommand, SyncUsersCommand

class AppServiceProvider(Provider):
    def boot(self) -> None:
        self.commands([GreetCommand, SyncUsersCommand])
```

The provider must be registered in `bootstrap/application.py` for the commands to appear in `uv run artisan list`.
