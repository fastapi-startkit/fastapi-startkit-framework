import ast
from pathlib import Path
from types import SimpleNamespace

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.console.database_install_command import DatabaseInstallCommand, register_database_provider
from fastapi_startkit.foundation.app_provider import AppProvider

MULTILINE_BOOTSTRAP = """from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.logging import LogProvider
from config.app import AppConfig
from config.logging import LoggingConfig

app = Application(
    base_path=Path(__file__).resolve().parent.parent,
    config=AppConfig,
    providers=[
        (LogProvider, LoggingConfig)  # logging
    ],
)
"""


def run(base_path: Path, args: str = "") -> CommandTester:
    command = DatabaseInstallCommand()
    command.set_container(SimpleNamespace(base_path=base_path))  # type: ignore[arg-type]
    tester = CommandTester(command)
    tester.execute(args)
    return tester


def make_app(tmp_path: Path, bootstrap: str = MULTILINE_BOOTSTRAP) -> Path:
    (tmp_path / "bootstrap").mkdir()
    (tmp_path / "bootstrap/application.py").write_text(bootstrap)
    return tmp_path


def providers_of(source: str) -> list[str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.keyword) and node.arg == "providers":
            assert isinstance(node.value, ast.List)
            return [ast.unparse(item) for item in node.value.elts]
    raise AssertionError("providers keyword not found")


def test_installs_config_and_registers_provider(tmp_path):
    app = make_app(tmp_path)

    tester = run(app)

    assert tester.status_code == 0
    config = (app / "config/database.py").read_text()
    assert 'env("DB_CONNECTION", "sqlite")' in config
    assert "SQLiteConfig()" in config
    bootstrap = (app / "bootstrap/application.py").read_text()
    assert providers_of(bootstrap) == ["(LogProvider, LoggingConfig)", "(DatabaseProvider, DatabaseConfig)"]
    assert (
        "        (LogProvider, LoggingConfig),  # logging\n        (DatabaseProvider, DatabaseConfig),\n" in bootstrap
    )
    assert (
        "from config.logging import LoggingConfig\n"
        "from fastapi_startkit.masoniteorm import DatabaseProvider\n"
        "from config.database import DatabaseConfig\n"
    ) in bootstrap
    output = tester.io.fetch_output()
    assert "Created config/database.py" in output
    assert "Registered DatabaseProvider in bootstrap/application.py" in output


def test_second_run_changes_nothing(tmp_path):
    app = make_app(tmp_path)
    run(app)
    config = (app / "config/database.py").read_text()
    bootstrap = (app / "bootstrap/application.py").read_text()

    tester = run(app, "--driver postgres")

    assert tester.status_code == 0
    assert (app / "config/database.py").read_text() == config
    assert (app / "bootstrap/application.py").read_text() == bootstrap
    output = tester.io.fetch_output()
    assert "config/database.py already exists, skipped" in output
    assert "DatabaseProvider is already registered" in output


def test_force_overwrites_existing_config(tmp_path):
    app = make_app(tmp_path)
    (app / "config").mkdir()
    (app / "config/database.py").write_text("OLD = True\n")

    tester = run(app, "--driver mysql --force")

    assert tester.status_code == 0
    assert "MySQLConfig()" in (app / "config/database.py").read_text()


def test_rejects_unknown_driver(tmp_path):
    app = make_app(tmp_path)

    tester = run(app, "--driver oracle")

    assert tester.status_code == 1
    assert "Unsupported driver 'oracle'" in tester.io.fetch_error()
    assert not (app / "config").exists()


def test_missing_bootstrap_prints_manual_steps(tmp_path):
    tester = run(tmp_path)

    assert tester.status_code == 1
    assert (tmp_path / "config/database.py").exists()
    error = tester.io.fetch_error()
    assert "Could not find Application(providers=[...]) in bootstrap/application.py" in error
    assert "from fastapi_startkit.masoniteorm import DatabaseProvider" in error


def test_single_line_providers_list():
    source = "from fastapi_startkit import Application\n\napp = Application(providers=[LogProvider, Other])\n"

    updated = register_database_provider(source)

    assert updated is not None
    assert "Application(providers=[LogProvider, Other, (DatabaseProvider, DatabaseConfig)])" in updated


def test_single_line_providers_list_with_trailing_comma_and_empty_list():
    assert "providers=[A, (DatabaseProvider, DatabaseConfig)]" in (
        register_database_provider("app = Application(providers=[A,])\n") or ""
    )
    assert "providers=[(DatabaseProvider, DatabaseConfig)]" in (
        register_database_provider("app = Application(providers=[])\n") or ""
    )


def test_adds_providers_keyword_when_missing():
    source = "from fastapi_startkit import Application\n\napp = Application(\n    base_path=None\n)\n"

    updated = register_database_provider(source)

    assert updated is not None
    assert "    base_path=None,\n    providers=[(DatabaseProvider, DatabaseConfig)],\n)" in updated
    assert providers_of(updated) == ["(DatabaseProvider, DatabaseConfig)"]


def test_adds_imports_to_file_without_imports():
    updated = register_database_provider("app = fastapi_startkit.Application()\n")

    assert updated is not None
    assert updated.startswith("from fastapi_startkit.masoniteorm import DatabaseProvider\n")
    assert "Application(providers=[(DatabaseProvider, DatabaseConfig)])" in updated


def test_keeps_existing_imports():
    source = (
        "from fastapi_startkit.masoniteorm.providers import DatabaseProvider\n"
        "from config.database import DatabaseConfig\n"
        "app = Application(providers=[])\n"
    )

    updated = register_database_provider(source)

    assert updated is not None
    assert updated.count("import DatabaseProvider") == 1
    assert updated.count("import DatabaseConfig") == 1


def test_unsupported_bootstrap_shapes_return_none():
    assert register_database_provider("app = object()\n") is None
    assert register_database_provider("app = Application(providers=PROVIDERS)\n") is None


def test_edited_bootstrap_compiles(tmp_path):
    app = make_app(tmp_path)

    run(app)

    compile((app / "bootstrap/application.py").read_text(), "application.py", "exec")


def test_app_provider_registers_command():
    application = SimpleNamespace(commands=[])
    application.add_commands = application.commands.extend

    AppProvider(application).boot()  # type: ignore[arg-type]

    assert DatabaseInstallCommand in application.commands
