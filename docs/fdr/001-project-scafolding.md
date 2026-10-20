# Project scaffolding

Status: Installer implemented for web applications with optional database and React/Vue frontends; available through uvx after the next package release. Queue support, existing-project installation, and the hosted shell bootstrap remain future work.

Related proposal: [PR #288 — project scaffolding](https://github.com/fastapi-startkit/fastapi-startkit-framework/pull/288). The initial proposal is implemented by the standalone `init` command. It uses a standalone Cleo CLI, bundled templates, a generation plan, and database selection. The new-project command is `init`; any existing-project `install` workflow remains separate.

## Goal

Start with one command, answer a few questions, and receive an application configured for the selected features. Users should not need to create a directory, initialize a uv project, or choose framework extras manually.

## Entry points

For users who already have uv, the command after release is:

```shell
uvx fastapi-startkit init
```

Users can optionally supply a project directory:

```shell
uvx fastapi-startkit init example-project
```

`uvx` runs a command supplied by a package in an isolated tool environment. Since the package and executable share the name `fastapi-startkit`, no `--from` option is needed ([uv tools guide](https://docs.astral.sh/uv/guides/tools/)). Users need uv installed, but do not need to install fastapi-startkit first. The package provides a `fastapi-startkit` console entry point backed by a bare Cleo application that runs before a framework application exists. For development before publication, run `uvx --from /path/to/built.whl fastapi-startkit init example-project`.

A future macOS/Linux bootstrap can provide the requested shell experience. The following illustrates its shape; `HOST` must be replaced by an actual project-controlled host before publication:

```shell
/bin/bash -c "$(curl -fsSL https://HOST/install.sh)"
```

The bootstrap locates uv or installs it using its [official installer](https://docs.astral.sh/uv/getting-started/installation/), then launches a versioned release of the same wizard. Newly installed uv must be usable in the current process without restarting the terminal. Keep interactive input connected to the terminal. Windows users with uv use the same uvx entry point; a native bootstrap can follow later.

## Interactive flow

```text
Project directory? example-project

App?
  > web

Database?
    none
  > sqlite
    postgres
    mysql

Frontend?
  > none
    react
    vue

Create this application?
  > Yes
    No

Creating application...
Installing Python dependencies...

Your application is ready.
```

Skip the directory question when it was supplied as an argument. Default to a web application with no frontend. Selecting a queue-only application skips frontend selection and generates no HTTP server or frontend files. The combined choice configures both services.

Worker and combined choices describe the intended experience after queue support ships. Until framework queue support is implemented, offer only the web choice and reject worker requests before creating files. Database selection is independent of application type and defaults to SQLite; choosing None omits ORM configuration and dependencies.

The summary shows the resolved destination, selected features, files, extras, and dependency commands before file generation. Declining exits without creating the project. Show dependency installation steps only when applicable, and report success only after they finish. As in PR #288, print frontend installation commands for the user to run instead of installing Node dependencies during scaffolding.

## Generated application

| Selection | Generated setup |
|---|---|
| All applications | Standalone `pyproject.toml`, Python version pin, `uv.lock` after dependency installation, `.env.example`, local `.env`, `artisan`, bootstrap, configuration, providers, storage, and a minimal smoke test |
| Web | FastAPI dependency extra, HTTP provider, routes, and a working health endpoint |
| SQLite/PostgreSQL/MySQL | Database and driver extras, typed database configuration, migrations, seeders, and driver-specific environment keys; SQLite also gets its database directory |
| Worker | TaskIQ and its Redis transport, broker configuration through environment variables, worker entry point, and an example task |
| Web + worker | Both setups, sharing application configuration (future work) |
| React or Vue | Inertia and Vite integration, selected frontend dependencies in `package.json`, root HTML template, and a working welcome page; frontend installation creates the lockfile |

Use available starter files as references, `example/queue-app/` as a TaskIQ reference, and the existing Inertia/Vite examples for frontend integration. Ship normalized `string.Template` stubs inside the package wheel, as proposed in PR #288, rather than fetching examples at runtime. TaskIQ is currently an example integration, not a framework extra; enable the worker template only after framework queue support is available. Each frontend needs its own validated template before it is offered in a released wizard.

Generate only the dependencies, providers, and files required by the chosen features. Worker output includes Redis connection instructions; frontend output lists its supported Node.js prerequisite. Do not install Node.js or start Redis automatically. Node.js is required when the user runs the printed frontend commands.

Finish with the actual commands for the selected template. For web applications, this includes:

```shell
cd example-project
uv run python artisan serve
```

Frontend applications also receive `npm install` and `npm run dev`. Worker applications receive their worker command and broker setup instructions. Combined applications explain that the HTTP server and worker run in separate terminals.

## Command behavior

- Accept a new or empty destination directory; refuse a nonempty directory without overwriting files.
- Keep existing-project installation separate: PR #288's `install` workflow proposes preserving files, merging missing environment keys, and printing provider changes for user-owned bootstrap code. Its overwrite and feature-addition behavior needs explicit validation before shipping.
- Support paths containing spaces and keep generated project metadata valid independently of the directory name.
- Use templates compatible with the installer release and published dependencies, without local workspace references.
- Leave the parent shell's working directory unchanged and print the next `cd` command.
- On installation failure, report the failed step and a retry command; preserve generated files for recovery.
- Support `--app web|worker|both`, `--database none|sqlite|postgres|mysql`, `--frontend none|react|vue`, and `--no-interaction`. Flags answer their corresponding questions; prompt only for remaining choices. In noninteractive mode, require a destination, apply documented defaults, and skip confirmation. Reject a worker/frontend mismatch or unavailable queue support before writing files.
- Support `--dry-run` to show the complete plan without writing files or installing dependencies.
- Support `--no-deps` to generate files and print dependency commands instead of installing Python dependencies. Explain that the environment and `uv.lock` will be ready only after those commands run.

Automation example after release:

```shell
uvx fastapi-startkit init example-project --app web --database sqlite --frontend vue --no-interaction
```

## Implementation

The standalone CLI lives in `fastapi_startkit.installer`. `InstallOptions` is validated before `build_plan()` composes `define_base()`, `define_database()`, `define_web()`, and `define_frontend()`. Each function returns an independent section containing its templates, imports, providers, dependencies, and environment settings. `render_sections()` combines those sections and renders bundled `.stub` files; `define_metadata()` supplies project metadata. The writer rechecks the destination before using exclusive file creation. A frontend app receives a fresh session secret in `.env`; `.env.example` keeps a placeholder.

Generated metadata pins the framework to the installer version and includes only the selected extras. Dependency installation runs `uv sync` in the destination, installing the generated project and creating `uv.lock`. `--no-deps` prints this command instead. Frontend dependency installation remains manual.

Focused unit tests cover each section and their composition. Validation also covers all twelve database/frontend combinations, generated HTTP and Inertia responses, SQLite migrations, file preservation, interactive prompts, failures, and dry runs. React and Vue templates must also pass production builds; the built wheel must expose the command and include all templates.
