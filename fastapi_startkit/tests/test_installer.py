import ast
import itertools
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from cleo.testers.command_tester import CommandTester

from fastapi_startkit.installer.cli import create_cli
from fastapi_startkit.installer.plan import InstallOptions, build_plan
from fastapi_startkit.installer.writer import write_plan


@pytest.fixture
def tester():
    cli = create_cli()
    cli.auto_exits(False)
    return CommandTester(cli.find("init"))


@pytest.mark.parametrize(
    "database,frontend", itertools.product(("none", "sqlite", "postgres", "mysql"), ("none", "react", "vue"))
)
def test_plan_matrix(tmp_path, database, frontend):
    options = InstallOptions(tmp_path / "My project!", database=database, frontend=frontend)
    plan = build_plan(options)
    assert plan == build_plan(options)
    assert not plan.directory.exists()
    metadata = tomllib.loads(plan.files["pyproject.toml"])
    assert metadata["project"]["name"] == "my-project"
    assert metadata["project"]["dependencies"] == [plan.dependency]
    assert ("config/database.py" in plan.files) == (database != "none")
    assert ("package.json" in plan.files) == (frontend != "none")
    assert "[tool.uv.sources]" not in plan.files["pyproject.toml"]
    for name, text in plan.files.items():
        if name.endswith(".py") or name == "artisan":
            ast.parse(text, filename=name)
    if frontend != "none":
        assert json.loads(plan.files["package.json"])["name"] == "my-project"
        assert "InertiaProvider" in plan.files["bootstrap/application.py"]
    write_plan(plan)
    assert (plan.directory / "artisan").stat().st_mode & 0o111
    with pytest.raises(ValueError, match="empty directory"):
        write_plan(plan)


@pytest.mark.parametrize(
    "flags,message",
    [
        ("--app worker", "Queue support"),
        ("--app both", "Queue support"),
        ("--app invalid", "--app must"),
        ("--database invalid", "--database must"),
        ("--frontend invalid", "--frontend must"),
        ("--app worker --frontend react", "cannot have a frontend"),
    ],
)
def test_invalid_choices_do_not_write(tmp_path, tester, flags, message):
    destination = tmp_path / "project"
    assert tester.execute(f"{destination} {flags} -n --no-deps") == 1
    assert message in tester.io.fetch_error()
    assert not destination.exists()


@pytest.mark.parametrize(
    "name,expected", [("!!!", "startkit-app"), ("FastAPI Startkit", "fastapi-startkit-app"), ("pytest", "pytest-app")]
)
def test_project_names_do_not_conflict_with_dependencies(tmp_path, name, expected):
    metadata = tomllib.loads(build_plan(InstallOptions(tmp_path / name)).files["pyproject.toml"])
    assert metadata["project"]["name"] == expected


def test_no_interaction_requires_directory(tester):
    assert tester.execute("-n --no-deps") == 1
    assert "destination directory is required" in tester.io.fetch_error()


def test_dry_run_has_no_side_effects(tmp_path, tester):
    destination = tmp_path / "project"
    with patch("fastapi_startkit.installer.init_command.subprocess.run") as run:
        assert tester.execute(f"{destination} -n --dry-run --frontend react") == 0
    run.assert_not_called()
    assert not destination.exists()
    output = tester.io.fetch_output()
    assert "create pyproject.toml" in output
    assert "inertia" in output
    assert "npm install" in output


def test_nonempty_and_file_destinations_are_preserved(tmp_path, tester):
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("user data")
    assert tester.execute(f"{tmp_path} -n --no-deps") == 1
    assert sentinel.read_text() == "user data"
    assert tester.execute(f"{sentinel} -n --no-deps") == 1
    assert sentinel.read_text() == "user data"


def test_symlink_destination_is_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        build_plan(InstallOptions(link))
    assert not list(actual.iterdir())


def test_writer_rechecks_destination(tmp_path):
    destination = tmp_path / "project"
    plan = build_plan(InstallOptions(destination))
    destination.mkdir()
    (destination / "user.txt").write_text("keep")
    with pytest.raises(ValueError, match="empty directory"):
        write_plan(plan)
    assert (destination / "user.txt").read_text() == "keep"


def test_no_deps_and_spaces(tmp_path, tester):
    destination = tmp_path / "project with spaces"
    before = Path.cwd()
    with patch("fastapi_startkit.installer.init_command.subprocess.run") as run:
        assert tester.execute(f'"{destination}" -n --no-deps') == 0
    run.assert_not_called()
    assert not (destination / "uv.lock").exists()
    assert "Run uv sync" in tester.io.fetch_output()
    assert Path.cwd() == before


def test_dependency_install(tmp_path, tester):
    destination = tmp_path / "project"
    with (
        patch("fastapi_startkit.installer.init_command.shutil.which", return_value="/bin/uv"),
        patch(
            "fastapi_startkit.installer.init_command.subprocess.run", return_value=subprocess.CompletedProcess([], 0)
        ) as run,
    ):
        assert tester.execute(f"{destination} -n") == 0
    run.assert_called_once_with(["uv", "sync"], cwd=destination, check=False)
    assert "Your application is ready" in tester.io.fetch_output()


@pytest.mark.parametrize("failure", [subprocess.CompletedProcess([], 1), OSError("unavailable")])
def test_dependency_failure_preserves_files(tmp_path, tester, failure):
    destination = tmp_path / "project"
    kwargs = {"side_effect": failure} if isinstance(failure, OSError) else {"return_value": failure}
    with (
        patch("fastapi_startkit.installer.init_command.shutil.which", return_value="/bin/uv"),
        patch("fastapi_startkit.installer.init_command.subprocess.run", **kwargs),
    ):
        assert tester.execute(f"{destination} -n") == 1
    assert (destination / "artisan").is_file()
    assert "retry uv sync" in tester.io.fetch_error()
    assert "Your application is ready" not in tester.io.fetch_output()


def test_missing_uv_fails_before_writing(tmp_path, tester):
    destination = tmp_path / "project"
    with patch("fastapi_startkit.installer.init_command.shutil.which", return_value=None):
        assert tester.execute(f"{destination} -n") == 1
    assert not destination.exists()
    assert "--no-deps" in tester.io.fetch_error()


def test_confirmation_can_cancel(tmp_path, tester):
    destination = tmp_path / "project"
    assert (
        tester.execute(
            f"{destination} --app web --database none --frontend none --no-deps", inputs="n\n", interactive=True
        )
        == 0
    )
    assert not destination.exists()


def test_interactive_prompts(tmp_path, tester):
    destination = tmp_path / "project"
    assert tester.execute("--no-deps", inputs=f"{destination}\n0\n0\n0\ny\n", interactive=True) == 0
    assert "config/database.py" not in [str(p.relative_to(destination)) for p in destination.rglob("*.py")]
    assert (destination / "artisan").exists()


def test_sessions_get_unique_secrets(tmp_path):
    secrets = []
    for name in ("first", "second"):
        plan = build_plan(InstallOptions(tmp_path / name, frontend="vue"))
        write_plan(plan)
        env = (plan.directory / ".env").read_text()
        assert "SESSION_SECRET=change-me" not in env
        assert "SESSION_SECRET=change-me" in (plan.directory / ".env.example").read_text()
        secrets.append(env.split("SESSION_SECRET=")[1].strip())
    assert secrets[0] != secrets[1]


@pytest.mark.parametrize(
    "database,frontend", itertools.product(("none", "sqlite", "postgres", "mysql"), ("none", "react", "vue"))
)
def test_generated_application(tmp_path, database, frontend):
    plan = build_plan(InstallOptions(tmp_path / "outside workspace", database=database, frontend=frontend))
    write_plan(plan)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("APP_", "DB_", "SESSION_"))}
    source = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(source)
    code = """from fastapi.testclient import TestClient
from bootstrap.application import app
with TestClient(app.fastapi) as client:
    response = client.get('/health')
    assert response.status_code == 200, response.text
    assert response.json() == {'status': 'ok'}
"""
    if frontend != "none":
        code += """    page = client.get('/', headers={'X-Inertia': 'true'})
    assert page.status_code == 200, page.text
    assert page.json()['component'] == 'Home'
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=plan.directory, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(
        [sys.executable, "artisan", "list"], cwd=plan.directory, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "serve" in result.stdout
    if database == "sqlite":
        result = subprocess.run(
            [sys.executable, "artisan", "db:migrate"], cwd=plan.directory, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (plan.directory / "databases/database.sqlite").exists()
