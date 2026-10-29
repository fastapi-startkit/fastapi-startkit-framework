# 033. Generated seeders have an async run

Date: 2026-10-21

## Problem

The `seed` command writes table seeders from `create_seed.stub`. The stub has a synchronous `def run(self)` and docstrings. `Seeder.call`, `run_database_seed` and `run_specific_seed` all `await ...run()`, so every generated seeder fails when it is seeded:

```
TypeError: 'NoneType' object can't be awaited
```

## Alternatives

1. Make `Seeder` accept both forms by awaiting the result only when it is awaitable. This would keep blocking seeders working, but seeders write through the async ORM, so a synchronous `run` cannot await queries anyway.
2. Make the stub match the async seeder API.

## Decision

Option 2. The stub generates `async def run(self) -> None` with no docstrings. The import, `from fastapi_startkit.masoniteorm.seeders import Seeder`, is already correct and stays. `Seeder` is unchanged.

## Validation

- A new test generates `PostTableSeeder` with `MakeSeedCommand`, checks the import, the `async def run` and that there are no docstrings, and imports it through `Seeder.run_specific_seed`, which awaits `run()`.
- The test fails on the old stub.
- Running the old stub's output through `run_specific_seed` raises the `TypeError` above.
