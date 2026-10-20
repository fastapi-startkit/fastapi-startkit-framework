import json
import re
from dataclasses import dataclass, field
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from string import Template


@dataclass(frozen=True)
class InstallOptions:
    directory: Path
    app: str = "web"
    database: str = "sqlite"
    frontend: str = "none"


@dataclass(frozen=True)
class Plan:
    directory: Path
    files: dict[str, str]
    dependency: str
    frontend: str


@dataclass(frozen=True)
class Section:
    templates: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    imports: tuple[str, ...] = ()
    providers: tuple[str, ...] = ()
    extras: tuple[str, ...] = ()
    environment: dict[str, str] = field(default_factory=dict)
    substitutions: dict[str, str] = field(default_factory=dict)


def validate_options(options: InstallOptions) -> None:
    if options.app not in ("web", "worker", "both"):
        raise ValueError("--app must be web, worker, or both.")
    if options.database not in ("none", "sqlite", "postgres", "mysql"):
        raise ValueError("--database must be none, sqlite, postgres, or mysql.")
    if options.frontend not in ("none", "react", "vue"):
        raise ValueError("--frontend must be none, react, or vue.")
    if options.app == "worker" and options.frontend != "none":
        raise ValueError("A worker application cannot have a frontend.")
    if options.app != "web":
        raise ValueError("Queue support is not available in this version. Use --app web.")


def validate_destination(directory: Path) -> None:
    if directory.is_symlink():
        raise ValueError(f"Destination must not be a symbolic link: {directory}")
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError(f"Destination must be a new or empty directory: {directory}")


def project_name_for(directory: Path) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", directory.name.lower()).strip("-") or "startkit-app"
    return f"{name}-app" if name in {"fastapi-startkit", "pytest", "httpx"} else name


def define_base(project_name: str) -> Section:
    return Section(
        templates={
            "artisan": "base/artisan",
            "bootstrap/application.py": "base/bootstrap.py",
            "config/app.py": "base/app.py",
            "config/logging.py": "base/logging.py",
            ".gitignore": "base/gitignore",
            "README.md": "base/README.md",
        },
        files={
            **{f"{package}/__init__.py": "" for package in ("bootstrap", "config", "providers", "routes", "tests")},
            "storage/logs/.gitignore": "*\n!.gitignore\n",
        },
        imports=(
            "from fastapi_startkit import Application",
            "from fastapi_startkit.logging import LogProvider",
            "from config.app import AppConfig",
            "from config.logging import LoggingConfig",
        ),
        providers=("(LogProvider, LoggingConfig)",),
        environment={
            "APP_NAME": project_name,
            "APP_ENV": "development",
            "APP_DEBUG": "true",
            "APP_URL": "http://127.0.0.1:8000",
        },
        substitutions={"project_name": project_name, "middleware": "", "entry": "", "react_refresh": ""},
    )


def define_web() -> Section:
    return Section(
        templates={
            "config/fastapi.py": "base/fastapi.py",
            "providers/fastapi_provider.py": "base/provider.py",
            "routes/api.py": "base/routes.py",
            "tests/test_application.py": "base/test_application.py",
        },
        imports=(
            "from config.fastapi import FastAPIConfig",
            "from providers.fastapi_provider import FastapiProvider",
        ),
        providers=("(FastapiProvider, FastAPIConfig)",),
        extras=("fastapi",),
    )


def define_database(driver: str, project_name: str) -> Section:
    if driver == "none":
        return Section()
    driver_class = {"sqlite": "SQLiteConfig", "postgres": "PostgresConfig", "mysql": "MySQLConfig"}[driver]
    environment = {"DB_CONNECTION": driver}
    if driver == "sqlite":
        environment["DB_DATABASE"] = "databases/database.sqlite"
    else:
        environment.update(
            {
                "DB_HOST": "127.0.0.1",
                "DB_PORT": "5432" if driver == "postgres" else "3306",
                "DB_DATABASE": project_name.replace("-", "_"),
                "DB_USERNAME": "postgres" if driver == "postgres" else "root",
                "DB_PASSWORD": "",
            }
        )
    return Section(
        templates={
            "config/database.py": "database/config.py",
            "databases/seeders/database_seeder.py": "database/seeder.py",
        },
        files={
            "databases/migrations/.gitkeep": "",
            "databases/seeders/__init__.py": "",
            "databases/__init__.py": "",
        },
        imports=(
            "from fastapi_startkit.masoniteorm import DatabaseProvider",
            "from config.database import DatabaseConfig",
        ),
        providers=("(DatabaseProvider, DatabaseConfig)",),
        extras=("database", driver),
        environment=environment,
        substitutions={"driver": driver, "driver_class": driver_class},
    )


def define_frontend(frontend: str) -> Section:
    if frontend == "none":
        return Section()
    extension = "tsx" if frontend == "react" else "ts"
    page = "Home.tsx" if frontend == "react" else "Home.vue"
    return Section(
        templates={
            "routes/api.py": "frontend/routes.py",
            "config/vite.py": "frontend/config.py",
            "resources/templates/index.html": "frontend/index.html",
            "resources/css/app.css": "frontend/app.css",
            "vite.config.ts": f"{frontend}/vite.config.ts",
            "package.json": f"{frontend}/package.json",
            f"resources/js/app.{extension}": f"{frontend}/app.{extension}",
            f"resources/js/Pages/{page}": f"{frontend}/{page}",
        },
        imports=(
            "from fastapi_startkit.inertia import InertiaProvider",
            "from fastapi_startkit.vite import ViteProvider",
            "from config.vite import ViteConfig",
            "from starlette.middleware.sessions import SessionMiddleware",
            "from fastapi_startkit.environment import value, env",
        ),
        providers=("(ViteProvider, ViteConfig)", "InertiaProvider"),
        extras=("inertia", "vite"),
        environment={"SESSION_SECRET": "change-me"},
        substitutions={
            "middleware": 'app.add_middleware(SessionMiddleware, secret_key=value(env("SESSION_SECRET", "")))\n',
            "entry": f"resources/js/app.{extension}",
            "react_refresh": "{{ vite_react_refresh() }}" if frontend == "react" else "",
        },
    )


def define_metadata(project_name: str, dependency: str) -> dict[str, str]:
    return {
        "pyproject.toml": f"""[project]
name = {json.dumps(project_name)}
version = "0.1.0"
requires-python = ">=3.12,<4.0"
dependencies = [{json.dumps(dependency)}]

[dependency-groups]
dev = ["pytest>=8", "httpx>=0.28"]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
""",
        ".python-version": "3.12\n",
    }


def render_sections(sections: tuple[Section, ...]) -> dict[str, str]:
    selected = {path: stub for section in sections for path, stub in section.templates.items()}
    substitutions = {key: value for section in sections for key, value in section.substitutions.items()}
    substitutions["imports"] = "\n".join(line for section in sections for line in section.imports)
    substitutions["providers"] = ",\n        ".join(provider for section in sections for provider in section.providers)
    stubs = files("fastapi_startkit.installer").joinpath("stubs")
    rendered = {
        path: Template(stubs.joinpath(stub + ".stub").read_text(encoding="utf-8")).substitute(substitutions)
        for path, stub in selected.items()
    }
    rendered.update({path: content for section in sections for path, content in section.files.items()})
    environment = {key: value for section in sections for key, value in section.environment.items()}
    rendered[".env.example"] = "".join(f"{key}={value}\n" for key, value in environment.items())
    rendered[".env"] = rendered[".env.example"]
    return rendered


def build_plan(options: InstallOptions) -> Plan:
    validate_options(options)
    directory = options.directory.expanduser().absolute()
    validate_destination(directory)
    project_name = project_name_for(directory)
    sections = (
        define_base(project_name),
        define_database(options.database, project_name),
        define_web(),
        define_frontend(options.frontend),
    )
    extras = {extra for section in sections for extra in section.extras}
    dependency = f"fastapi-startkit[{','.join(sorted(extras))}]=={version('fastapi-startkit')}"
    rendered = render_sections(sections)
    rendered.update(define_metadata(project_name, dependency))
    return Plan(directory, rendered, dependency, options.frontend)
