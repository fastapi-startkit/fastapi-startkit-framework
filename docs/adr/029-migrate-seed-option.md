# 029. db:migrate:fresh and db:migrate:refresh --seed run seeders in the same event loop

Date: 2026-10-21

## Problem

`db:migrate:fresh --seed <value>` and `db:migrate:refresh --seed <value>` failed after migrating:

```
$ python artisan db:migrate:fresh --seed null
The command "seed:run" does not exist.
```

There are three faults:

- Both commands called `seed:run`, but the seed command is registered as `db:seed`.
- Renaming the call would still fail. Cleo's `Command.call` binds its arguments against the application definition, and that definition's first positional argument is `command`. So the first argument would be read as the command name.
- The call ran inside `handle_async`, which is already running under `asyncio.run`. `DBSeedCommand.handle` calls `asyncio.run` again, and that raises `RuntimeError` when a loop is already running.

`db:migrate:refresh` was also never registered, so `artisan` could not run it at all.

## Alternatives

1. Rename the call to `db:seed`, put the command name first, and make the call after `asyncio.run` returns. This keeps a nested console dispatch and runs the seeders in a second event loop, separate from the one used for migrating.
2. Move the seeder selection out of `DBSeedCommand.handle_async` into an async `DBSeedCommand.run_seeders`, and await it from all three commands.

## Decision

Option 2. Seeding runs in the same event loop as migrating, with no console re-dispatch and no argument string to parse. `db:seed` keeps its arguments, options and output, and the selection rules (`--class`, table argument, `DatabaseSeeder`) live in one place.

`--seed null` runs `DatabaseSeeder`. `--seed <table>` runs `<Table>TableSeeder`. Both behave as before, and `--seed-directory` and `--connection` are passed through.

`DatabaseProvider` registers `MigrateRefreshCommand` next to `MigrateFreshCommand`.

## Validation

- New console-path tests use `app.run(...)` on an app booted with `DatabaseProvider`, which is the path `artisan` uses. They use a fixture migration that creates the table the fixture seeders write to:
  - `db:migrate:fresh --seed null` runs `DatabaseSeeder`.
  - `db:migrate:fresh --seed user` runs `UserTableSeeder`.
  - `db:migrate:refresh --seed null` runs `DatabaseSeeder`, which also proves the command is registered.
- All three tests fail without the fix. The existing `db:seed` tests pass unchanged.
- In a project created with `uvx fastapi-startkit init`, both `python artisan db:migrate:fresh --seed null` and `python artisan db:migrate:refresh --seed null` migrate and seed.

## Out of scope

The seeder stub `create_seed.stub` generates a synchronous `run` that has a docstring. `Seeder` awaits `run()`, so a generated table seeder raises `TypeError` when it runs. Fixing the stub belongs in its own record.
