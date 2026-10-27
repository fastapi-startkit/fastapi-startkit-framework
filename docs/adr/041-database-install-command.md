# 041. InstallCommand base class and database:install

Date: 2026-10-22

## Problem

`fastapi-startkit init --database ...` sets up the database only for new projects. An existing application without a database has to copy a config file and edit `bootstrap/application.py` by hand: import `DatabaseProvider` and its config, and add `(DatabaseProvider, DatabaseConfig)` to `providers=[...]`. `provider:publish` cannot help, because it only knows about the resources of providers that are already registered and booted.

Other packages (cache, broadcasting, storage, ...) need the same steps: publish a config file and register their provider in `bootstrap/application.py`. If the AST editing lives inside the database command, each package would have to copy it.

## Alternatives

1. Register the command from `DatabaseProvider`. It would only exist after the database is installed, which is too late.
2. Generate a provider list in a separate file such as `config/providers.py`. Apps do not use one. Every app built with the installer and every example lists providers inline in the `Application(...)` call in `bootstrap/application.py`.
3. Add a core command, registered by `AppProvider` next to `provider:publish`, that writes the config file and edits `bootstrap/application.py` in place.
4. Option 3, with the bootstrap edit as a module-level function that each command calls directly. This shares the logic, but every command would repeat the `--force` option, the publish-or-skip handling, and the error/manual-steps output.
5. Option 3, with a reusable `InstallCommand` base class.

## Decision

Option 5. `fastapi_startkit/console/install_command.py` defines `InstallCommand(Command)` with a fluent class builder:

```python
CacheInstallCommand = (
    InstallCommand.register("cache:install", "Install the cache.")
    .copy(files("my_package").joinpath("stubs/cache.py"), "config/cache.py")
    .add_provider(CacheProvider, "config.cache.CacheConfig")
)
```

- `register(name, description)`, `copy(stub, destination)` and `add_provider(provider, config=None)` are classmethods. Each one returns a new subclass with the added attributes and leaves the receiver unchanged. The result is a command class, which is what `Provider.commands([...])` expects.
- `add_provider` takes classes or dotted strings. A class is converted to `module.QualName`. A string is needed when the class lives in the user's app (`config.database.DatabaseConfig` does not exist when the framework loads), or when importing it would load an optional extra. Each `ProviderEntry` derives the inserted entry (`(Provider, Config)`, or a bare `Provider` when there is no config) and the `from module import Name` statements.
- `copy` accepts a path or an `importlib.resources` `Traversable` and copies the stub verbatim.
- `handle()` runs `publish()` and then registers every provider. The default `publish()` copies each stub. A subclass that needs options or templating overrides `publish()` and calls `publish_file(relative_path, content)`. `publish_file` creates parent directories and skips an existing file unless `--force` is passed. `--force` is declared on the base class, and subclasses add their own options with `options = [*InstallCommand.options, ...]`.
- `register_provider(source, provider, entry, imports)` is a pure function that returns the edited source, the unchanged source if the provider is already registered, or `None` if there is no `Application(providers=[...])` to edit.

`DatabaseInstallCommand` is a regular subclass, because it has a `--driver` option and renders the stub template. It declares `providers = (ProviderEntry.of("fastapi_startkit.masoniteorm.DatabaseProvider", "config.database.DatabaseConfig"),)`. `uv run artisan database:install [--driver sqlite|postgres|mysql] [--force]`:

- Renders `config/database.py` from the installer's `database/config.py.stub`, so it matches what `fastapi-startkit init` generates. `config/` is created if missing. If the file already exists it is skipped with a message, unless `--force` is passed.
- Parses `bootstrap/application.py` with `ast` and finds the `Application(...)` call. If its `providers` list already names `DatabaseProvider`, nothing is changed. Otherwise `(DatabaseProvider, DatabaseConfig)` is appended to the list, following its layout: a new line for multi-line lists, inline for single-line lists. If there is no `providers=` keyword, one is added. Missing `from fastapi_startkit.masoniteorm import DatabaseProvider` and `from config.database import DatabaseConfig` imports are inserted after the last top-level import.
- If `bootstrap/application.py` or the `Application(...)` call is missing, it prints the lines to add by hand and returns 1. The config file is still written.

The command lives in `fastapi_startkit/console/` rather than `masoniteorm/commands/`, because importing `masoniteorm.commands` loads SQLAlchemy, which is an optional extra. `install_command.py` imports only `ast`, cleo and `Command`, so packages with optional extras can subclass it without loading anything extra. Text is inserted at AST-reported positions rather than regenerated with `ast.unparse`, so the user's formatting and comments are kept.

## Validation

- `tests/console/test_install_command.py` tests commands built with the fluent API: a copied stub with a tuple entry, a provider-only command with a bare entry, several providers with a `Traversable` stub, class references converted to imports, and chain calls that do not mutate the base class. It also tests `register_provider` directly on single-line, multi-line, empty and missing `providers` lists, files with no imports, existing imports, already-registered providers and unsupported shapes.
- `tests/console/test_database_install_command.py` runs `database:install` against a temporary app directory. It covers a fresh install, a second run that changes nothing, an existing config with and without `--force`, a missing `config/` directory, a missing bootstrap file, an unsupported driver, and loading the edited bootstrap file.
- The full suite passes with coverage of at least 80%.
- Manual run, twice, against an app generated by `fastapi-startkit init --database none`.
