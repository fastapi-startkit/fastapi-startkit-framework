import ast
import json
import tomllib

import pytest

from fastapi_startkit.installer.plan import (
    Section,
    define_base,
    define_database,
    define_frontend,
    define_metadata,
    define_web,
    render_sections,
)


def test_base_has_no_optional_integrations():
    section = define_base("example-app")
    assert not section.extras
    assert section.environment["APP_NAME"] == "example-app"
    assert "artisan" in section.templates
    assert "SESSION_SECRET" not in section.environment
    assert not any(key.startswith("DB_") for key in section.environment)
    assert all(
        "DatabaseProvider" not in provider and "InertiaProvider" not in provider for provider in section.providers
    )


def test_web_defines_http_routes_and_server_provider():
    section = define_web()
    assert section.extras == ("fastapi",)
    assert "routes/api.py" in section.templates
    assert "tests/test_application.py" in section.templates
    assert "(FastapiProvider, FastAPIConfig)" in section.providers


def test_no_database_adds_nothing():
    assert define_database("none", "example-app") == Section()


@pytest.mark.parametrize(
    "driver,config_class",
    [
        ("sqlite", "SQLiteConfig"),
        ("postgres", "PostgresConfig"),
        ("mysql", "MySQLConfig"),
    ],
)
def test_database_defines_driver_and_migrations(driver, config_class):
    section = define_database(driver, "example-app")
    assert set(section.extras) == {"database", driver}
    assert section.environment["DB_CONNECTION"] == driver
    assert section.substitutions["driver_class"] == config_class
    assert "config/database.py" in section.templates
    assert "databases/seeders/database_seeder.py" in section.templates
    assert "databases/migrations/.gitkeep" in section.files
    assert "(DatabaseProvider, DatabaseConfig)" in section.providers


def test_sqlite_needs_no_server_credentials():
    environment = define_database("sqlite", "example-app").environment
    assert environment == {"DB_CONNECTION": "sqlite", "DB_DATABASE": "databases/database.sqlite"}


@pytest.mark.parametrize("driver,port,username", [("postgres", "5432", "postgres"), ("mysql", "3306", "root")])
def test_server_database_defaults(driver, port, username):
    environment = define_database(driver, "example-app").environment
    assert environment["DB_HOST"] == "127.0.0.1"
    assert environment["DB_PORT"] == port
    assert environment["DB_DATABASE"] == "example_app"
    assert environment["DB_USERNAME"] == username
    assert environment["DB_PASSWORD"] == ""


def test_no_frontend_adds_nothing():
    assert define_frontend("none") == Section()


@pytest.mark.parametrize(
    "frontend,entry,page,package",
    [
        ("react", "resources/js/app.tsx", "resources/js/Pages/Home.tsx", "@inertiajs/react"),
        ("vue", "resources/js/app.ts", "resources/js/Pages/Home.vue", "@inertiajs/vue3"),
    ],
)
def test_frontend_defines_matching_inertia_assets(frontend, entry, page, package):
    section = define_frontend(frontend)
    assert set(section.extras) == {"inertia", "vite"}
    assert entry in section.templates
    assert page in section.templates
    assert section.substitutions["entry"] == entry
    assert section.environment["SESSION_SECRET"] == "change-me"
    assert section.providers.index("(ViteProvider, ViteConfig)") < section.providers.index("InertiaProvider")
    rendered = render_sections((define_base("example-app"), define_web(), section))
    assert package in json.loads(rendered["package.json"])["dependencies"]
    assert "Inertia.render" in rendered["routes/api.py"]
    assert entry in rendered["resources/templates/index.html"]


@pytest.mark.parametrize("frontend,has_refresh", [("react", True), ("vue", False)])
def test_react_refresh_is_included_only_for_react(frontend, has_refresh):
    rendered = render_sections((define_base("example-app"), define_frontend(frontend)))
    assert ("vite_react_refresh()" in rendered["resources/templates/index.html"]) == has_refresh


def test_render_sections_combines_providers_without_losing_http_or_database():
    rendered = render_sections(
        (
            define_base("example-app"),
            define_database("sqlite", "example-app"),
            define_web(),
            define_frontend("react"),
        )
    )
    bootstrap = rendered["bootstrap/application.py"]
    ast.parse(bootstrap)
    assert bootstrap.index("(DatabaseProvider, DatabaseConfig)") < bootstrap.index("(FastapiProvider, FastAPIConfig)")
    assert bootstrap.index("(ViteProvider, ViteConfig)") < bootstrap.index("InertiaProvider,")
    assert "SessionMiddleware" in bootstrap
    assert "DB_DATABASE=databases/database.sqlite\n" in rendered[".env"]
    assert "SESSION_SECRET=change-me\n" in rendered[".env"]
    assert rendered[".env"] == rendered[".env.example"]
    assert "databases/migrations/.gitkeep" in rendered


def test_definitions_do_not_share_mutable_defaults():
    first = define_database("none", "first")
    first.files["custom.py"] = "custom"
    assert "custom.py" not in define_frontend("none").files
    assert "custom.py" not in define_database("none", "second").files


def test_metadata_creates_standalone_project_with_exact_dependency():
    dependency = "fastapi-startkit[database,fastapi,sqlite]==1.2.3"
    files = define_metadata("example-app", dependency)
    metadata = tomllib.loads(files["pyproject.toml"])
    assert metadata["project"]["name"] == "example-app"
    assert metadata["project"]["dependencies"] == [dependency]
    assert metadata["tool"]["uv"] == {"package": False}
    assert metadata["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert files[".python-version"] == "3.12\n"


@pytest.mark.parametrize("frontend", ["none", "react", "vue"])
async def test_routes_bind_controller_actions(frontend):
    rendered = render_sections((define_base("example-app"), define_web(), define_frontend(frontend)))
    namespace = {}
    exec(compile(rendered["routes/api.py"], "routes/api.py", "exec"), namespace)
    controller = namespace["controller"]
    routes = {route.path: route.endpoint for route in namespace["router"].router.routes}
    assert routes["/"].__self__ is controller
    assert routes["/health"].__self__ is controller
    assert await routes["/health"]() == {"status": "ok"}
    if frontend == "none":
        assert await routes["/"]() == {"message": "Welcome to FastAPI Startkit"}
    else:
        response = await routes["/"]()
        assert response.component == "Home"
