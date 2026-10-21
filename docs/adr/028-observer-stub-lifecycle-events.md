# 028. Observer and model stubs import, make:observer is registered, and make:model flags work

- Date: 2026-10-21
- Status: Accepted

## Problem

`observer.stub`, rendered by `MakeObserverCommand`, imports `Model` from `masoniteorm.models`, a package that is not installed with the framework, so any generated observer that is imported fails with `ModuleNotFoundError`. It stubs `booted`, `booting`, `hydrating` and `hydrated`, which the model never dispatches, and every method carries a Google-style docstring, which the coding standards forbid. ADR 025 defined the events that are dispatched (`saving`, `creating`, `updating`, `created`, `updated`, `saved`, `deleting`, `deleted`) and awaits async handlers.

`model.stub`, rendered by `db:make:model`, has the same `masoniteorm.models` import, so every generated model fails on import, and it carries docstrings too. `MakeObserverCommand` is exported but no provider registers it, so `artisan` cannot run it; its name is `observer`, unlike the `db:make:migration` and `db:make:model` commands that `DatabaseProvider` registers.

Both `db:make:model` flags that chain to another command fail on 0.67.0. `--migration` calls `migration`, but the command is registered as `db:make:migration` (`The command "migration" does not exist.`). `--seeder` calls the registered `seed` command but still fails with `Not enough arguments (missing: "name")`. Cleo's `Command.call(name, args)` binds `args` against the merged application definition, whose first positional argument is `command`, so the first word of `args` is taken as the command name and the real first argument goes missing.

## Alternatives

1. **Fix only the import.** Smallest change, but users keep getting handlers that never fire, plus the docstrings.
2. **Import the generated model class for the type hint.** More precise typing, but the model module and its path are not known to the command, and the observer would fail to import when the model does not exist yet.
3. **Import `Model` from `fastapi_startkit.masoniteorm.models` and stub exactly the dispatched events as async methods.** Always importable, and the handlers match what fires.

## Decision

Option 3. The stub imports `Model` from `fastapi_startkit.masoniteorm.models` and defines `async def <event>(self, <model>: Model) -> None` for the eight lifecycle events in dispatch order. It has no docstrings or comments. Handlers are async because the ORM is async-first and `observe_events` awaits them, so a handler can query the database. Sync handlers still work for users who prefer them.

`model.stub` imports `Model` from the same module and drops its docstrings. `MakeObserverCommand` is renamed `db:make:observer`, following the `db:make:*` convention, and `DatabaseProvider.boot()` registers it next to `MakeModelCommand`. The old `observer` name was never reachable from `artisan`, so the rename breaks nothing.

`db:make:model` calls `db:make:migration` for `--migration`. Its nested calls go through a `call_command(name, arguments)` method that passes `f"{name} {arguments}"`, so the name fills Cleo's `command` slot and the arguments bind as intended. The prefix stays local to `MakeModelCommand` rather than overriding `call` on the console `Command` base, because this is the only working caller and the base class is core framework code.

## Implementation

- `masoniteorm/commands/stubs/observer.stub` is rewritten; `MakeObserverCommand` is unchanged.
- `masoniteorm/commands/stubs/model.stub` is rewritten to the corrected import and a bare `pass` body.
- `MakeObserverCommand.name` is `db:make:observer`; `DatabaseProvider` imports and registers it.
- `MakeModelCommand` builds the migration arguments once and sends both nested calls through `call_command`.
- Audit of nested `call` uses in `masoniteorm/commands`: the make commands' only chained calls are the two in `db:make:model`, both fixed. Not changed here: `db:migrate:fresh --seed` and `db:migrate:refresh --seed` call `seed:run`, which does not exist (the seeder is `db:seed`). They hit the same positional-argument problem, and they call it from inside `asyncio.run`, where `db:seed` would start a second event loop. `db:migrate:refresh` is also not registered. Fixing them needs the seeding moved out of the running loop plus new fixtures, so it needs its own record.

## Validation

- `tests/masoniteorm/commands/test_make_commands.py` checks the import line, the async typed signature, and that the file has no docstrings or comments. It also loads the generated file with `importlib`, asserts that its handlers are exactly the eight events in order, and dispatches each event through `observe_events` on a `Model` subclass.
- A model test generates `app/Post.py`, checks the import line and the absence of docstrings, then loads the file and asserts that the class subclasses `Model`.
- A console test boots an application with `DatabaseProvider` and runs `app.run("db:make:observer", "Order")`, the same `ConsoleApplication` path that `artisan` uses. It fails when the registration is removed.
- Console tests run `db:make:model Post --migration`, `--migration --table` and `--seeder` through `app.run`, and check the generated create/update migration and seeder. All three fail without the name prefix.
- In a project created with `uvx fastapi-startkit init` and run against the local build, `python artisan db:make:model Invoice` and `python artisan db:make:observer Invoice` created `app/Invoice.py` and `app/observers/InvoiceObserver.py`, and both imported. `python artisan db:make:model Receipt --migration --seeder` created the model, migration and seeder, and `python artisan db:migrate` applied the migration. On 0.67.0, the same flags fail with the two errors above.
