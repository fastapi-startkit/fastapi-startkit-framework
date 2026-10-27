import ast
from pathlib import Path
from types import SimpleNamespace

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.console.database_install_command import DatabaseInstallCommand
from fastapi_startkit.console.install_command import InstallCommand
from fastapi_startkit.foundation.app_provider import AppProvider

BOOTSTRAP = """from pathlib import Path

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


def make_app(tmp_path: Path) -> Path:
    (tmp_path / "bootstrap").mkdir()
    (tmp_path / "bootstrap/application.py").write_text(BOOTSTRAP)
    return tmp_path


def providers_of(source: str) -> list[str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.keyword) and node.arg == "providers":
            assert isinstance(node.value, ast.List)
            return [ast.unparse(item) for item in node.value.elts]
    raise AssertionError("providers keyword not found")


def test_is_an_install_command():
    assert issubclass(DatabaseInstallCommand, InstallCommand)


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
        "from config.logging import LoggingConfig\n"
        "from fastapi_startkit.masoniteorm import DatabaseProvider\n"
        "from config.database import DatabaseConfig\n"
    ) in bootstrap
    compile(bootstrap, "application.py", "exec")
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
    bootstrap = (app / "bootstrap/application.py").read_text()

    tester = run(app, "--driver oracle")

    assert tester.status_code == 1
    assert "Unsupported driver 'oracle'" in tester.io.fetch_error()
    assert not (app / "config").exists()
    assert (app / "bootstrap/application.py").read_text() == bootstrap


def test_missing_bootstrap_prints_manual_steps(tmp_path):
    tester = run(tmp_path)

    assert tester.status_code == 1
    assert (tmp_path / "config/database.py").exists()
    assert "from fastapi_startkit.masoniteorm import DatabaseProvider" in tester.io.fetch_error()


def test_app_provider_registers_command():
    application = SimpleNamespace(commands=[])
    application.add_commands = application.commands.extend

    AppProvider(application).boot()  # type: ignore[arg-type]

    assert DatabaseInstallCommand in application.commands
