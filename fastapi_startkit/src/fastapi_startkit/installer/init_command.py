import shlex
import shutil
import subprocess
from pathlib import Path

from cleo.commands.command import Command
from cleo.helpers import argument, option

from .plan import InstallOptions, build_plan, validate_options
from .writer import write_plan


class InitCommand(Command):
    name = "init"
    description = "Create a FastAPI Startkit application."
    arguments = [argument("directory", "New or empty project directory", optional=True)]
    options = [
        option("app", description="web, worker, or both", flag=False),
        option("database", description="none, sqlite, postgres, or mysql", flag=False),
        option("frontend", description="none, react, or vue", flag=False),
        option("dry-run", description="Show the plan without creating files"),
        option("no-deps", description="Generate files without installing Python dependencies"),
    ]

    def handle(self) -> int:
        try:
            return self.create_project()
        except (ValueError, OSError) as error:
            self.line_error(str(error), style="error")
            return 1

    def create_project(self) -> int:
        interactive = self.io.is_interactive() and not self.option("no-interaction")
        directory = self.argument("directory")
        if not directory:
            if not interactive:
                raise ValueError("A destination directory is required with --no-interaction.")
            directory = self.ask("Project directory?", default="example-project")
        selections = {
            "app": self.option("app") or "web",
            "database": self.option("database") or "sqlite",
            "frontend": self.option("frontend") or "none",
        }
        validate_options(InstallOptions(Path(directory), **selections))
        if interactive:
            for name, choices in (
                ("app", ["web"]),
                ("database", ["none", "sqlite", "postgres", "mysql"]),
                ("frontend", ["none", "react", "vue"]),
            ):
                if self.option(name) is None:
                    selections[name] = self.choice(
                        f"{name.capitalize()}?", choices, default=choices.index(selections[name]), attempts=3
                    )
        plan = build_plan(InstallOptions(Path(directory), **selections))
        command = ["uv", "sync"]
        self.line(f"Destination: {plan.directory}")
        self.line(
            f"Application: {selections['app']}; database: {selections['database']}; frontend: {selections['frontend']}"
        )
        for name in sorted(plan.files):
            self.line(f"  create {name}")
        self.line(f"Dependency: {plan.dependency}")
        self.line("Python dependencies: uv sync")
        if plan.frontend != "none":
            self.line("Frontend dependencies: npm install (run after generation; requires Node.js 22.12+)")
        if self.option("dry-run"):
            return 0
        if interactive and not self.confirm("Create this application?", default=True):
            return 0
        if not self.option("no-deps") and shutil.which("uv") is None:
            raise ValueError("uv is required to install dependencies. Install uv or pass --no-deps.")
        write_plan(plan)
        self.line("Application files created.")
        self.line(f"Next: cd {shlex.quote(str(plan.directory))}")
        if self.option("no-deps"):
            self.line("Run uv sync to install dependencies and create uv.lock.")
        else:
            self.line("Installing Python dependencies...")
            try:
                result = subprocess.run(command, cwd=plan.directory, check=False)
            except OSError as error:
                self.line_error(
                    f"Dependency installation failed: {error}. Files preserved; retry uv sync in the project directory.",
                    style="error",
                )
                return 1
            if result.returncode:
                self.line_error(
                    "Dependency installation failed. Files preserved; retry uv sync in the project directory.",
                    style="error",
                )
                return 1
            self.line("Your application is ready.")
        self.line("Run: uv run python artisan serve")
        if plan.frontend != "none":
            self.line("In another terminal: npm install && npm run dev (Node.js 22.12+).")
        if selections["database"] in ("postgres", "mysql"):
            self.line("Configure database credentials in .env and start the database server before migrating.")
        if selections["database"] != "none":
            self.line("Migrate: uv run python artisan db:migrate")
        return 0
