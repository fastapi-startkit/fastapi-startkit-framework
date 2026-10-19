# 022. Interactive `fastapi-startkit install` scaffolding command

- Date: 2026-10-18
- Status: Proposed

## Problem

A new project starts with `uv add fastapi-startkit`, and then the user has nothing to run. They have to copy `bootstrap/`, `config/`, `providers/`, `routes/` and `artisan` by hand from one of the `example/*` apps, and work out which extras (`fastapi`, `database`, `sqlite`/`postgres`/`mysql`, `vite`, `inertia`) go with which providers.

The repository doesn't help much here:

- `AGENTS.md` describes an `application/` starter template, and `[tool.uv] workspace.members` lists `application`, but the directory isn't there. There's no canonical starter to copy.
- The `example/*` apps aren't in the wheel, and they don't agree with each other. `base_path` is computed three different ways, and `DatabaseProvider` is imported from two different modules.
- The package has no console-script entry point. Every Cleo command today runs through a project's own `artisan`, which needs a booted `Application`, so no command can run before a project exists.

The goal is one command, run after `uv add fastapi-startkit`:

```bash
uv run fastapi-startkit install
```

It asks what the project needs and writes a runnable skeleton.

## Alternatives

| Option | Pros | Cons |
|---|---|---|
| **Copier / cookiecutter template repo** | Mature templating and conditionals, and Copier can update an existing project | Adds a runtime dependency (Copier pulls in jinja2, questionary, plumbum and more) or needs `uvx copier`. The template lives in a second repo or URL and drifts from the framework version. It doesn't fit the Cleo/artisan style the framework uses, and it's a poor fit for "add a feature to an existing project" |
| **`git clone` / copy `application/`** | Zero code | All-or-nothing, with no choices. `application/` doesn't exist. Extras still have to be added by hand. Not idempotent |
| **Cleo `install` command shipped in the package, with stubs bundled in the wheel** (chosen) | No new dependency (Cleo is already core). Templates are versioned with the framework they target. It reuses the existing `Command` and `confirm`/`choice` helpers. It's testable with Cleo's `CommandTester`. It can re-run on an existing project to add a feature | Conditional file composition has to be maintained in Python, and template upgrades for existing projects are out of scope |

## Decision

### Entry point

Add a console script to `fastapi_startkit/pyproject.toml`:

```toml
[project.scripts]
fastapi-startkit = "fastapi_startkit.installer.cli:main"
```

(The request said `fastapi-starkit`. That's assumed to be a typo for `fastapi-startkit`, which matches the PyPI name.)

`main()` builds a bare `cleo.application.Application("fastapi-startkit", __version__)` and registers `InstallCommand`. It doesn't construct a framework `Application`, because there's no project to boot yet. That means `InstallCommand` subclasses `cleo.commands.command.Command` directly, not `fastapi_startkit.console.Command`, which expects a container. Because the CLI has its own entry point, `uvx fastapi-startkit install` also works before `uv add`.

### Question flow

```
1. HTTP API with FastAPI?               [Y/n]            --http / --no-http
2. Database?                            none|sqlite|postgres|mysql  (default sqlite)
                                                          --database=<driver>
3. Background queue (taskiq)?           [y/N]            --queue / --no-queue
4. Frontend?                            none|vite|inertia (default none)
                                                          --frontend=<kind>
   (asked only if HTTP = yes; inertia implies vite)
5. Show plan (files to create/skip, extras to add) -> "Proceed?" [Y/n]
```

- Each question is skipped when its flag is given, so flags and prompts can be mixed.
- Cleo's built-in `-n/--no-interaction` answers every remaining question with its default and skips the confirmation: `fastapi-startkit install -n --database=postgres --frontend=inertia`.
- Other options:
  - `--path=<dir>` (default `.`)
  - `--force` (overwrite files that already exist)
  - `--dry-run` (print the plan and exit)
  - `--no-deps` (don't run `uv add`; print the command instead)
- Invalid combinations fail before any file is written, with a non-zero exit code. Examples are `--frontend=vite --no-http` and an unknown `--database`.

### Generated files per answer

Every file is rendered from `fastapi_startkit/installer/stubs/` with `string.Template`, so no new dependency is needed. `bootstrap/application.py` is assembled from the chosen provider list and isn't stored as one stub per combination.

| Answer | Files | Extras added |
|---|---|---|
| always | `artisan` (executable, `sys.exit(app.handle_command())`), `bootstrap/__init__.py`, `bootstrap/application.py`, `config/__init__.py`, `config/app.py`, `config/logging.py`, `providers/__init__.py`, `storage/logs/.gitignore`, `.env`, `.env.example`, `.gitignore` additions | none (core) |
| HTTP | `config/fastapi.py`, `providers/fastapi_provider.py`, `routes/__init__.py`, `routes/api.py` (a `GET /` health route) | `fastapi` |
| Database = sqlite | `config/database.py` (`SQLiteConfig`), `databases/migrations/.gitkeep`, `databases/seeders/database_seeder.py`; `.env`: `DB_CONNECTION=sqlite`, `DB_DATABASE=databases/database.sqlite` | `database`, `sqlite` |
| Database = postgres / mysql | `config/database.py` (`PostgresConfig` / `MySQLConfig`), migrations, seeders; `.env`: `DB_HOST/PORT/DATABASE/USERNAME/PASSWORD` | `database`, `postgres` / `mysql` |
| Queue | `config/queue.py`, `tasks/__init__.py`, `tasks/example_task.py`, `worker.py` (exposes `broker`) | `queue` (new, see below) |
| Frontend = vite | `config/vite.py`, `resources/views/app.html`, `resources/js/app.ts`, `vite.config.ts`, `package.json` | `vite` |
| Frontend = inertia | everything vite generates, plus `resources/js/Pages/Home.(tsx\|vue)`, the `InertiaProvider` registration, and session middleware in the FastAPI provider | `inertia`, `vite` |

Extras are applied by running `uv add "fastapi-startkit[<sorted, comma-joined extras>]"` in the target directory, so `pyproject.toml` and `uv.lock` stay consistent and the step is idempotent. If `uv` isn't on `PATH`, or `--no-deps` is set, the command is printed instead. Node dependencies are never installed; the closing "next steps" message tells the user to run `npm install && npm run dev`.

### Reuse of `application/` and `example/`

The stubs are the single source of truth, and they ship in the wheel because `example/` doesn't. To stop them drifting from the examples:

1. **Phase 1:** write the stubs from the current examples (`fastapi-app` for HTTP, `database-app` for the ORM, `vite-app`/`inertia-pingcrm-app` for the frontend, `queue-app` for taskiq), normalised to one style: `base_path=Path(__file__).resolve().parent.parent` and imports from public package `__init__`s only.
2. **Repurpose `application/`:** instead of a hand-maintained directory, it becomes the output of `fastapi-startkit install -n --database=sqlite` committed to the repo. A test regenerates it and fails on any diff, so the workspace member exists again and always matches the stubs.
3. Examples stay as feature showcases. They aren't rewritten in this change.

### Taskiq support (new scope)

There's no taskiq support in the framework today. `facades/Queue.py` binds the key `queue`, but nothing registers it; the `.pyi` stub is a leftover Masonite queue API. Only `example/queue-app` uses taskiq, through an app-local `QueueProvider`. That provider registers broker startup/shutdown with the deprecated `on_event`, and its `queue:work` command is app-local too.

The proposal is a minimal `fastapi_startkit.queue` package, with its own ADR and PR before the installer offers the question:

- An optional extra `queue = ["taskiq>=0.11", "taskiq-redis>=1.0"]`, with taskiq imported lazily the way `redis` is.
- `QueueConfig(Config)`: `driver = env("QUEUE_DRIVER", "memory")` (`memory` → `InMemoryBroker`, `redis` → `ListQueueBroker` plus `RedisAsyncResultBackend`), and `url = env("QUEUE_URL", "redis://localhost:6379")`.
- `QueueProvider`: binds `broker` and `queue`. It starts and stops the broker by wrapping the router lifespan, the same way `RedisProvider` does in ADR 005, not with `on_event`.
- `QueueWorkCommand` (`queue:work [--workers N]`), registered by the provider. It runs `taskiq worker worker:broker` with task-module discovery.
- `Queue.pyi` is rewritten to the broker surface, and the Masonite leftovers are removed.

Until that lands, the installer leaves out question 3, and `--queue` fails with "queue support not available in this version".

### Non-empty directory and idempotency

- Before writing, the command builds a **plan**: every target file is marked `create`, `skip (exists)` or `overwrite (--force)`. The plan is shown before the confirmation and is the whole output of `--dry-run`.
- Existing files are never overwritten without `--force`. In interactive mode, a file that already exists and differs from the stub gets a per-file `confirm(..., default=False)`, the same pattern as `provider:publish`.
- `bootstrap/application.py` is the exception. If it already exists and wasn't generated by the installer, the installer doesn't edit it. It prints the provider lines to add by hand, because rewriting a user's bootstrap safely would mean editing Python source.
- `.env` and `.env.example` are **merged**: missing keys are appended, and existing keys are left alone.
- `uv add` with extras that are already present is a no-op.
- So running the command twice with the same answers changes nothing. Running it again with a new feature, for example `--database=postgres` on an HTTP-only project, adds only that feature's files and extras.
- A directory that holds only `pyproject.toml`, `uv.lock`, `.venv`, `.git`, `README.md`, `.python-version` or `main.py` (what `uv init` creates) counts as empty. A `main.py` from `uv init` is left in place.

## Implementation (after approval)

1. `fastapi_startkit/installer/`:
   - `cli.py` (`main`)
   - `install_command.py` (questions and flags into an `InstallOptions` dataclass)
   - `plan.py` (pure `build_plan(options, target) -> Plan` with files and extras)
   - `writer.py` (applies the plan and merges `.env`)
   - `stubs/`
2. `[project.scripts]` entry. Stubs are included in the wheel; `uv_build` includes package data under `src/` by default, and this is checked on the built wheel.
3. Regenerate `application/`, and add its drift test.
4. Docs: a "Installation" section in `fastapi_startkit.github.io.git/docs/getting-started`.
5. A separate ADR and PR for `fastapi_startkit.queue`, then enable question 3.

## Validation

- **Unit:** `build_plan` is covered by a parametrised matrix (http × database × frontend × queue): file set, extras, and rejected combinations. It's pure, so it needs no I/O.
- **Command:** Cleo's `CommandTester` with scripted inputs and with `-n` plus flags, writing into `tmp_path`. Asserts cover the files created, the exit codes, and the `uv add` argv; the subprocess is stubbed.
- **Idempotency:**
  - A second run produces only `skip` entries and leaves file contents byte-identical.
  - `.env` keeps user edits and gains only new keys.
  - `--force` overwrites.
  - A user-owned `bootstrap/application.py` is never modified.
- **Smoke:** for a representative subset (http+sqlite, http+postgres, http+inertia, console-only), generate the project, import `bootstrap.application` with the dev-group dependencies installed, and assert:
  - `artisan list` exits 0;
  - for HTTP, `GET /` through `httpx.ASGITransport` returns 200;
  - for sqlite, `artisan migrate` runs.
- **Packaging:** after `uv build`, the wheel contains `installer/stubs/**` and exposes the `fastapi-startkit` script. `uvx --from dist/*.whl fastapi-startkit install -n --dry-run` exits 0.
- **Drift:** `application/` equals a fresh `install -n --database=sqlite` output.
- Coverage stays at or above the 80% `fail_under`.
