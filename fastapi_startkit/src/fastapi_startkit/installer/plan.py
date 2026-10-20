import json
import re
from dataclasses import dataclass
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


def build_plan(options: InstallOptions) -> Plan:
    validate_options(options)
    directory = options.directory.expanduser().absolute()
    validate_destination(directory)
    project_name = re.sub(r"[^a-z0-9]+", "-", directory.name.lower()).strip("-") or "startkit-app"
    if project_name in {"fastapi-startkit", "pytest", "httpx"}:
        project_name += "-app"
    extras = {"fastapi"}
    imports = [
        "from fastapi_startkit import Application",
        "from fastapi_startkit.logging import LogProvider",
        "from config.app import AppConfig",
        "from config.fastapi import FastAPIConfig",
        "from config.logging import LoggingConfig",
        "from providers.fastapi_provider import FastapiProvider",
    ]
    providers = ["(LogProvider, LoggingConfig)", "(FastapiProvider, FastAPIConfig)"]
    selected = {
        "artisan": "base/artisan",
        "bootstrap/application.py": "base/bootstrap.py",
        "config/app.py": "base/app.py",
        "config/fastapi.py": "base/fastapi.py",
        "config/logging.py": "base/logging.py",
        "providers/fastapi_provider.py": "base/provider.py",
        "routes/api.py": "base/routes.py",
        "tests/test_application.py": "base/test_application.py",
        ".gitignore": "base/gitignore",
        "README.md": "base/README.md",
    }
    env = [f"APP_NAME={project_name}", "APP_ENV=development", "APP_DEBUG=true", "APP_URL=http://127.0.0.1:8000"]
    substitutions = {"project_name": project_name, "middleware": "", "entry": "", "react_refresh": ""}
    if options.database != "none":
        extras.update(("database", options.database))
        imports.extend(
            [
                "from fastapi_startkit.masoniteorm import DatabaseProvider",
                "from config.database import DatabaseConfig",
            ]
        )
        providers.insert(1, "(DatabaseProvider, DatabaseConfig)")
        driver_class = {"sqlite": "SQLiteConfig", "postgres": "PostgresConfig", "mysql": "MySQLConfig"}[
            options.database
        ]
        substitutions.update({"driver": options.database, "driver_class": driver_class})
        selected["config/database.py"] = "database/config.py"
        selected["databases/seeders/database_seeder.py"] = "database/seeder.py"
        env.append(f"DB_CONNECTION={options.database}")
        if options.database == "sqlite":
            env.append("DB_DATABASE=databases/database.sqlite")
        else:
            port = 5432 if options.database == "postgres" else 3306
            username = "postgres" if options.database == "postgres" else "root"
            env.extend(
                [
                    "DB_HOST=127.0.0.1",
                    f"DB_PORT={port}",
                    f"DB_DATABASE={project_name.replace('-', '_')}",
                    f"DB_USERNAME={username}",
                    "DB_PASSWORD=",
                ]
            )
    if options.frontend != "none":
        extras.update(("inertia", "vite"))
        imports.extend(
            [
                "from fastapi_startkit.inertia import InertiaProvider",
                "from fastapi_startkit.vite import ViteProvider",
                "from config.vite import ViteConfig",
                "from starlette.middleware.sessions import SessionMiddleware",
                "from fastapi_startkit.environment import value, env",
            ]
        )
        providers.extend(["(ViteProvider, ViteConfig)", "InertiaProvider"])
        env.append("SESSION_SECRET=change-me")
        substitutions["middleware"] = (
            'app.add_middleware(SessionMiddleware, secret_key=value(env("SESSION_SECRET", "")))\n'
        )
        extension = "tsx" if options.frontend == "react" else "ts"
        substitutions["entry"] = f"resources/js/app.{extension}"
        substitutions["react_refresh"] = "{{ vite_react_refresh() }}" if options.frontend == "react" else ""
        selected.update(
            {
                "routes/api.py": "frontend/routes.py",
                "config/vite.py": "frontend/config.py",
                "resources/templates/index.html": "frontend/index.html",
                "resources/css/app.css": "frontend/app.css",
                "vite.config.ts": f"{options.frontend}/vite.config.ts",
                "package.json": f"{options.frontend}/package.json",
                f"resources/js/app.{extension}": f"{options.frontend}/app.{extension}",
            }
        )
        page = "Home.tsx" if options.frontend == "react" else "Home.vue"
        selected[f"resources/js/Pages/{page}"] = f"{options.frontend}/{page}"
    substitutions.update({"imports": "\n".join(imports), "providers": ",\n        ".join(providers)})
    stubs = files("fastapi_startkit.installer").joinpath("stubs")
    rendered = {
        path: Template(stubs.joinpath(stub + ".stub").read_text(encoding="utf-8")).substitute(substitutions)
        for path, stub in selected.items()
    }
    for package in ("bootstrap", "config", "providers", "routes", "tests"):
        rendered[f"{package}/__init__.py"] = ""
    rendered["storage/logs/.gitignore"] = "*\n!.gitignore\n"
    if options.database != "none":
        rendered["databases/migrations/.gitkeep"] = ""
        rendered["databases/seeders/__init__.py"] = ""
        rendered["databases/__init__.py"] = ""
    dependency = f"fastapi-startkit[{','.join(sorted(extras))}]=={version('fastapi-startkit')}"
    rendered["pyproject.toml"] = f"""[project]
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
"""
    rendered[".python-version"] = "3.12\n"
    rendered[".env.example"] = "\n".join(env) + "\n"
    rendered[".env"] = rendered[".env.example"]
    return Plan(directory, rendered, dependency, options.frontend)
