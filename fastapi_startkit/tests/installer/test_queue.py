import ast
import itertools
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from fastapi_startkit.installer.cli import create_cli
from fastapi_startkit.installer.plan import InstallOptions, build_plan, define_queue
from fastapi_startkit.installer.writer import write_plan


@pytest.mark.parametrize("web", [False, True])
def test_queue_section_reuses_app_local_provider(web):
    section = define_queue(web=web)
    assert not section.extras
    assert set(section.dependencies) == {"taskiq>=0.11,<1", "taskiq-redis>=1,<2"}
    assert "worker.py" in section.templates
    assert "tasks/example_task.py" in section.templates
    assert section.environment["QUEUE_DRIVER"] == "redis"
    assert section.substitutions["manages_http_lifespan"] == str(web)


@pytest.mark.parametrize("app,database", itertools.product(("worker", "both"), ("none", "sqlite", "postgres", "mysql")))
def test_queue_plans_install_taskiq_and_preserve_optional_http(tmp_path, app, database):
    plan = build_plan(InstallOptions(tmp_path / "project", app=app, database=database))
    metadata = tomllib.loads(plan.files["pyproject.toml"])
    assert set(plan.dependencies) == set(metadata["project"]["dependencies"])
    assert "taskiq>=0.11,<1" in plan.dependencies
    assert "taskiq-redis>=1,<2" in plan.dependencies
    assert ("config/fastapi.py" in plan.files) == (app == "both")
    assert ("routes/api.py" in plan.files) == (app == "both")
    assert ("routes/__init__.py" in plan.files) == (app == "both")
    assert ("fastapi," in plan.dependency or "fastapi]" in plan.dependency) == (app == "both")
    assert "[]" not in plan.dependency
    for name, content in plan.files.items():
        if name.endswith(".py"):
            ast.parse(content, filename=name)


def test_worker_selector_skips_frontend(tmp_path):
    cli = create_cli()
    tester = CommandTester(cli.find("init"))
    path = tmp_path / "worker"
    assert tester.execute("--no-deps", inputs=f"{path}\n1\n0\ny\n", interactive=True) == 0
    assert "frontend" not in tester.io.fetch_error()
    assert not (path / "routes").exists()
    assert not (path / "package.json").exists()
    output = tester.io.fetch_output()
    assert "artisan queue:work" in output
    assert "artisan serve" not in output
    assert "taskiq-redis" in output


def test_selecting_both_services_creates_combined_app(tmp_path):
    cli = create_cli()
    tester = CommandTester(cli.find("init"))
    path = tmp_path / "both"
    assert tester.execute("--no-deps", inputs=f"{path}\n0,1\n0\n0\ny\n", interactive=True) == 0
    assert "HTTP server with FastAPI routes and a health check" in tester.io.fetch_error()
    assert (path / "routes").exists()
    assert (path / "worker.py").exists()
    output = tester.io.fetch_output()
    assert "artisan queue:work" in output
    assert "artisan serve" in output


@pytest.mark.parametrize("app,frontend", [("worker", "none"), ("both", "none"), ("both", "react"), ("both", "vue")])
def test_generated_queue_app_executes_tasks_and_owns_lifecycle(tmp_path, app, frontend):
    plan = build_plan(InstallOptions(tmp_path / "app", app=app, database="none", frontend=frontend))
    write_plan(plan)
    env_file = plan.directory / ".env"
    env_file.write_text(env_file.read_text().replace("QUEUE_DRIVER=redis", "QUEUE_DRIVER=memory"))
    source = Path(__file__).resolve().parents[2] / "src"
    env = {key: value for key, value in os.environ.items() if not key.startswith(("APP_", "DB_", "QUEUE_"))}
    env.update(PYTHONPATH=str(source), QUEUE_DRIVER="memory")
    code = """import asyncio
from unittest.mock import AsyncMock
from bootstrap.application import app
from worker import broker
from tasks.example_task import send_welcome_email

async def execute_task():
    task = await send_welcome_email.kiq('test@example.com', 'Test')
    result = await task.wait_result(timeout=5)
    assert result.return_value == {'status': 'sent', 'email': 'test@example.com', 'name': 'Test'}

async def main():
    assert app.make('queue') is broker
    broker.startup = AsyncMock(wraps=broker.startup)
    broker.shutdown = AsyncMock(wraps=broker.shutdown)
"""
    if app == "both":
        code += """    async with app.fastapi.router.lifespan_context(app.fastapi):
        await execute_task()
    broker.startup.assert_awaited_once()
    broker.shutdown.assert_awaited_once()
    broker.startup.reset_mock()
    broker.shutdown.reset_mock()
    broker.is_worker_process = True
    async with app.fastapi.router.lifespan_context(app.fastapi):
        pass
    broker.startup.assert_not_awaited()
    broker.shutdown.assert_not_awaited()
"""
    else:
        code += """    assert app._fastapi is None
    await broker.startup()
    try:
        await execute_task()
    finally:
        await broker.shutdown()
"""
    code += "\nasyncio.run(main())\n"
    result = subprocess.run([sys.executable, "-c", code], cwd=plan.directory, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for args in (["artisan", "list"], ["-m", "pytest", "tests", "-q"]):
        result = subprocess.run([sys.executable, *args], cwd=plan.directory, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        if args[0] == "artisan":
            assert "queue:work" in result.stdout


def test_queue_command_passes_worker_arguments_and_exit_code(tmp_path):
    plan = build_plan(InstallOptions(tmp_path / "app", app="worker", database="none"))
    namespace = {}
    exec(compile(plan.files["commands/queue_work_command.py"], "queue_work_command.py", "exec"), namespace)
    from unittest.mock import patch

    command = namespace["QueueWorkCommand"]()
    tester = CommandTester(command)
    with patch.object(namespace["subprocess"], "run", return_value=subprocess.CompletedProcess([], 7)) as run:
        assert tester.execute("--workers 3") == 7
    run.assert_called_once_with(
        [
            sys.executable,
            "-m",
            "taskiq",
            "worker",
            "worker:broker",
            "tasks.example_task",
            "--workers",
            "3",
        ],
        check=False,
    )
    with patch.object(namespace["subprocess"], "run") as run:
        assert tester.execute("--workers 0") == 1
        assert tester.execute("--workers invalid") == 1
    run.assert_not_called()
