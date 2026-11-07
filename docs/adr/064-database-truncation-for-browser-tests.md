# 064. Database truncation for browser tests

Date: 2026-11-07

Superseded in part by ADR 067: the live-server fixture and `LiveServer.run` are removed; `BrowserTestCase` awaits `asyncStartTestRun` on the shared session loop.

## Problem

Browser tests (ADR 063) drive an app served by uvicorn on its own thread and event loop. `RefreshDatabase` wraps each test in a transaction opened on the test's connection, but the server answers requests on its own connections and its own loop, so the rollback never covers what the browser wrote. Tests also cannot share a database safely without a reset: a sign-up test fails the second time it runs because the email already exists. Running every migration before every test is slow. `RefreshDatabase` also only hooks into `TestCase` (`asyncStartTestRun`), while browser test classes are plain sync classes.

## Alternatives

1. **Migrate fresh before every test.** Correct, but slow once the schema grows.
2. **Share one transaction between the test and the server.** Needs the server to reuse the test's connection across threads and loops, which async drivers (aiosqlite, asyncpg) do not allow.
3. **Truncate, like Laravel's `DatabaseTruncation`.** Migrate fresh on the first test of the run, then empty the tables before each later test.

## Decision

Option 3: `fastapi_startkit.masoniteorm.testing.DatabaseTruncation`.

- `truncate_database()` runs `Migrator.fresh(ignore_fk=True)` on the first call of the process. Later calls empty every table that `Schema.get_all_tables()` lists, with foreign key checks off, skipping `migrations`, SQLite internal `sqlite_*` tables and `except_tables`. When `tables_to_truncate` is set, only those tables are emptied.
- After the reset the database is seeded by default: `DatabaseSeeder` runs, or the seeder named by `seeder = "UserSeeder"`, through `DBSeedCommand.run_seeders`. `seed = False` turns seeding off. `seed_directory` defaults to `databases/seeders`, `migration_directory` to `databases/migrations`, both relative to the application base path. `connection` selects the connection (default connection when `None`).
- In plain sync test classes (browser tests), an autouse pytest fixture runs `truncate_database()` on the live server's event loop through the new `LiveServer.run(coroutine)`, which submits it with `asyncio.run_coroutine_threadsafe` and waits for the result. This starts the server if it is not running, so the database and the app share one loop and its connections. `LiveServer` now runs `uvicorn.Server.serve` under its own `asyncio.run` so it can keep a handle on the loop.
- `TestCase` subclasses (`IsolatedAsyncioTestCase`) skip the fixture and run `truncate_database()` from `asyncStartTestRun` in the test's own loop, like `RefreshDatabase`.
- The fixture is sync, so the plugin keeps the Playwright driver running between truncating browser tests (ADR 063).

## Validation

- `fastapi_startkit/tests/masoniteorm/testing/test_database_truncation.py` checks, on SQLite, that the first call migrates fresh and later calls empty tables but keep `migrations` and `except_tables`, that `tables_to_truncate` limits the reset, that seeding runs by default, `seeder` picks the seeder and `seed = False` skips it, and that a plain class resets the database through a live server's loop.
- `fastapi_startkit/tests/playwright/` checks `LiveServer.run` returns the coroutine's result and raises when the server is not running.
- The example's `RegistrationTest` uses `DatabaseTruncation` without any configuration, and its conftest no longer migrates by subprocess. The sign-up test passes when run repeatedly in one session.
