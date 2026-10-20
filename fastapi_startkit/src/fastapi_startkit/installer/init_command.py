import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from cleo.commands.command import Command
from cleo.helpers import argument, option

from .plan import InstallOptions, build_plan, validate_options
from .prompts import Choice, ClassicPrompts, Prompter, Terminal
from .writer import write_plan

SERVICES = [
    Choice("web", "Web", "HTTP server with FastAPI routes and a health check"),
    Choice("worker", "Worker", "TaskIQ background jobs with a Redis broker"),
]
DATABASES = [
    Choice("none", "None", "No ORM or migrations"),
    Choice("sqlite", "SQLite", "File-based, no server required"),
    Choice("postgres", "PostgreSQL", "asyncpg driver"),
    Choice("mysql", "MySQL", "aiomysql driver"),
]
FRONTENDS = [
    Choice("none", "None", "API only"),
    Choice("react", "React", "Inertia, React, TypeScript and Tailwind"),
    Choice("vue", "Vue", "Inertia, Vue, TypeScript and Tailwind"),
]


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
        except KeyboardInterrupt:
            self.line_error("Cancelled.", style="error")
            return 1

    def create_project(self) -> int:
        interactive = self.io.is_interactive() and not self.option("no-interaction")
        prompts = self.prompts() if interactive else None
        directory = self.argument("directory")
        if not directory:
            if prompts is None:
                raise ValueError("A destination directory is required with --no-interaction.")
            directory = prompts.text("Where should the project be created?", "example-project")
        selections = {
            "app": self.option("app") or "web",
            "database": self.option("database") or "sqlite",
            "frontend": self.option("frontend") or "none",
        }
        validate_options(InstallOptions(Path(directory), **selections))
        if prompts is not None:
            if self.option("app") is None:
                services = prompts.multiselect("Which services should your application run?", SERVICES, ["web"])
                selections["app"] = "both" if len(services) == len(SERVICES) else services[0]
            if self.option("database") is None:
                selections["database"] = prompts.select(
                    "Which database will your application use?", DATABASES, selections["database"]
                )
            if self.option("frontend") is None and selections["app"] != "worker":
                selections["frontend"] = prompts.select(
                    "Which frontend would you like to install?", FRONTENDS, selections["frontend"]
                )
        plan = build_plan(InstallOptions(Path(directory), **selections))
        command = ["uv", "sync"]
        self.line(f"Destination: {plan.directory}")
        self.line(
            f"Application: {selections['app']}; database: {selections['database']}; frontend: {selections['frontend']}"
        )
        for name in sorted(plan.files):
            self.line(f"  create {name}")
        for dependency in plan.dependencies:
            self.line(f"Dependency: {dependency}")
        self.line("Python dependencies: uv sync")
        if plan.frontend != "none":
            self.line("Frontend dependencies: npm install (run after generation; requires Node.js 22.12+)")
        if self.option("dry-run"):
            return 0
        if prompts is not None and not prompts.confirm("Create the application with these settings?", default=True):
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
        if selections["app"] != "worker":
            self.line("Run: uv run python artisan serve")
        if selections["app"] != "web":
            self.line("Start Redis at QUEUE_URL from .env, then run: uv run python artisan queue:work")
            if selections["app"] == "both":
                self.line("Run the HTTP server and queue worker in separate terminals.")
        if plan.frontend != "none":
            self.line("In another terminal: npm install && npm run dev (Node.js 22.12+).")
        if selections["database"] in ("postgres", "mysql"):
            self.line("Configure database credentials in .env and start the database server before migrating.")
        if selections["database"] != "none":
            self.line("Migrate: uv run python artisan db:migrate")
        return 0

    def prompts(self) -> Prompter | ClassicPrompts:
        stream = getattr(self.io.input, "stream", None) or sys.stdin
        if Terminal.supported(stream, sys.stdout):
            return Prompter(Terminal(stream, sys.stdout))
        return ClassicPrompts(self)
