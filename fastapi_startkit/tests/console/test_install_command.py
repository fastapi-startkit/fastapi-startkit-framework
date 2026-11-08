import ast
import re
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

import pytest
from cleo.testers.command_tester import CommandTester

from fastapi_startkit.console.install_command import InstallCommand, ProviderEntry, RegistrationError, register_provider
from fastapi_startkit.logging import LogProvider

IMPORTS = {"CacheProvider": "fastapi_startkit.cache", "CacheConfig": "config.cache"}

BOOTSTRAP = """from fastapi_startkit import Application
from config.logging import LoggingConfig

app = Application(
    providers=[
        (LogProvider, LoggingConfig)  # logging
    ],
)
"""


def cache_install(tmp_path: Path) -> type[InstallCommand]:
    stub = tmp_path / "cache.py.stub"
    stub.write_text("CACHE = True\n")
    return (
        InstallCommand.register("cache:install", "Install the cache.")
        .copy(stub, "config/cache.py")
        .add_provider("fastapi_startkit.cache.CacheProvider", "config.cache.CacheConfig")
    )


def provider_only_install() -> type[InstallCommand]:
    return InstallCommand.register("broadcast:install").add_provider("fastapi_startkit.broadcasting.BroadcastProvider")


def run(command_class: type[InstallCommand], base_path: Path, args: str = "") -> CommandTester:
    command = command_class()
    command.set_container(SimpleNamespace(base_path=base_path))  # type: ignore[arg-type]
    tester = CommandTester(command)
    tester.execute(args)
    return tester


def make_app(tmp_path: Path) -> Path:
    (tmp_path / "bootstrap").mkdir()
    (tmp_path / "bootstrap/application.py").write_text(BOOTSTRAP)
    return tmp_path


def register(source: str) -> str:
    return register_provider(source, "CacheProvider", "(CacheProvider, CacheConfig)", IMPORTS)


def providers_of(source: str) -> list[str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.keyword) and node.arg == "providers":
            assert isinstance(node.value, ast.List)
            return [ast.unparse(item) for item in node.value.elts]
    raise AssertionError("providers keyword not found")


def test_subclass_publishes_and_registers(tmp_path):
    app = make_app(tmp_path)

    tester = run(cache_install(tmp_path), app)

    assert tester.status_code == 0
    assert (app / "config/cache.py").read_text() == "CACHE = True\n"
    bootstrap = (app / "bootstrap/application.py").read_text()
    assert "        (LogProvider, LoggingConfig),  # logging\n        (CacheProvider, CacheConfig),\n" in bootstrap
    assert (
        "from config.logging import LoggingConfig\n"
        "from fastapi_startkit.cache import CacheProvider\n"
        "from config.cache import CacheConfig\n"
    ) in bootstrap
    output = tester.io.fetch_output()
    assert "Created config/cache.py" in output
    assert "Registered CacheProvider in bootstrap/application.py" in output


def test_second_run_changes_nothing(tmp_path):
    app = make_app(tmp_path)
    run(cache_install(tmp_path), app)
    bootstrap = (app / "bootstrap/application.py").read_text()

    tester = run(cache_install(tmp_path), app)

    assert tester.status_code == 0
    assert (app / "bootstrap/application.py").read_text() == bootstrap
    output = tester.io.fetch_output()
    assert "config/cache.py already exists, skipped" in output
    assert "CacheProvider is already registered" in output


def test_fluent_chain_builds_independent_command_classes():
    command = InstallCommand.register("log:install", "Install logging.").add_provider(
        LogProvider, "config.logging.LoggingConfig"
    )

    assert issubclass(command, InstallCommand)
    assert command.name == "log:install"
    assert command.description == "Install logging."
    assert InstallCommand.providers == ()
    assert command.providers == (
        ProviderEntry(f"{LogProvider.__module__}.LogProvider", "config.logging.LoggingConfig"),
    )


def test_provider_entry_from_class_derives_entry_and_imports():
    entry = ProviderEntry.of(LogProvider, "config.logging.LoggingConfig")

    assert entry.name == "LogProvider"
    assert entry.entry == "(LogProvider, LoggingConfig)"
    assert entry.imports == {"LogProvider": LogProvider.__module__, "LoggingConfig": "config.logging"}


def test_registers_multiple_providers_and_copies_traversable_stub(tmp_path):
    app = make_app(tmp_path)
    stub = files("fastapi_startkit.installer").joinpath("stubs/database/config.py.stub")
    command = (
        InstallCommand.register("multi:install")
        .copy(stub, "config/raw.py")
        .add_provider("package.AProvider")
        .add_provider("package.BProvider", "config.b.BConfig")
    )

    tester = run(command, app)

    assert tester.status_code == 0
    assert (app / "config/raw.py").read_text() == stub.read_text()
    assert providers_of((app / "bootstrap/application.py").read_text()) == [
        "(LogProvider, LoggingConfig)",
        "AProvider",
        "(BProvider, BConfig)",
    ]


def test_force_overwrites_published_file(tmp_path):
    app = make_app(tmp_path)
    (app / "config").mkdir()
    (app / "config/cache.py").write_text("OLD = True\n")

    run(cache_install(tmp_path), app, "--force")

    assert (app / "config/cache.py").read_text() == "CACHE = True\n"


def test_provider_without_config_and_without_publish(tmp_path):
    app = make_app(tmp_path)

    tester = run(provider_only_install(), app)

    assert tester.status_code == 0
    assert providers_of((app / "bootstrap/application.py").read_text()) == [
        "(LogProvider, LoggingConfig)",
        "BroadcastProvider",
    ]
    assert not (app / "config").exists()


def test_missing_bootstrap_prints_manual_steps(tmp_path):
    tester = run(cache_install(tmp_path), tmp_path)

    assert tester.status_code == 1
    assert (tmp_path / "config/cache.py").exists()
    error = tester.io.fetch_error()
    assert "bootstrap/application.py does not exist." in error
    assert "from fastapi_startkit.cache import CacheProvider" in error
    assert "Register CacheProvider manually:" in error
    assert "providers=[..., (CacheProvider, CacheConfig)]" in error


def test_single_line_providers_list():
    updated = register(
        "from fastapi_startkit import Application\n\napp = Application(providers=[LogProvider, Other])\n"
    )

    assert "Application(providers=[LogProvider, Other, (CacheProvider, CacheConfig)])" in updated


def test_single_line_providers_list_with_trailing_comma_and_empty_list():
    assert "providers=[A, (CacheProvider, CacheConfig)]" in register("app = Application(providers=[A,])\n")
    assert "providers=[(CacheProvider, CacheConfig)]" in register("app = Application(providers=[])\n")


def test_adds_providers_keyword_when_missing():
    updated = register("from fastapi_startkit import Application\n\napp = Application(\n    base_path=None\n)\n")

    assert "    base_path=None,\n    providers=[(CacheProvider, CacheConfig)],\n)" in updated
    assert providers_of(updated) == ["(CacheProvider, CacheConfig)"]


def test_adds_imports_to_file_without_imports():
    updated = register("app = fastapi_startkit.Application()\n")

    assert updated.startswith("from fastapi_startkit.cache import CacheProvider\n")
    assert "Application(providers=[(CacheProvider, CacheConfig)])" in updated


def test_keeps_existing_imports():
    source = (
        "from fastapi_startkit.cache import CacheProvider\n"
        "from config.cache import CacheConfig\n"
        "app = Application(providers=[])\n"
    )

    updated = register(source)

    assert updated.count("import CacheProvider") == 1
    assert updated.count("import CacheConfig") == 1


def test_already_registered_returns_source_unchanged():
    source = "app = Application(providers=[(CacheProvider, CacheConfig)])\n"

    assert register(source) == source


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("app = object()\n", "Could not find an Application(...) call."),
        ("app = Application(providers=PROVIDERS)\n", "providers is not a list literal."),
        ("app = Application('.', None, PROVIDERS)\n", "providers is not a list literal."),
        ("app = Application(*ARGS)\n", "Application(...) is called with *args."),
    ],
)
def test_unsupported_bootstrap_shapes_raise(source, message):
    with pytest.raises(RegistrationError, match=re.escape(message)):
        register(source)


@pytest.mark.parametrize(
    "item",
    ["(cache.CacheProvider, CacheConfig)", "fastapi_startkit.cache.CacheProvider", "(cache.CacheProvider, x.Config)"],
)
def test_attribute_reference_counts_as_registered(item):
    source = f"import cache\napp = Application(providers=[{item}])\n"

    assert register(source) == source


def test_inserts_into_positional_providers_list():
    updated = register("from fastapi_startkit import Application\n\napp = Application('.', None, [A])\n")

    assert "Application('.', None, [A, (CacheProvider, CacheConfig)])" in updated
    assert "providers=" not in updated


def test_positional_providers_already_registered_returns_source_unchanged():
    source = "app = Application('.', None, [CacheProvider])\n"

    assert register(source) == source


def test_name_imported_from_another_module_raises():
    source = "from fastapi_startkit.masoniteorm.config import CacheConfig\napp = Application(providers=[])\n"

    with pytest.raises(
        RegistrationError,
        match=re.escape(
            "CacheConfig is already imported as fastapi_startkit.masoniteorm.config.CacheConfig, not config.cache.CacheConfig."
        ),
    ):
        register(source)


def test_aliased_import_of_another_module_raises():
    source = "from other import Something as CacheProvider\napp = Application(providers=[])\n"

    with pytest.raises(
        RegistrationError,
        match="CacheProvider is already imported as other.Something, not fastapi_startkit.cache.CacheProvider.",
    ):
        register(source)


def test_relative_import_of_same_name_raises():
    source = "from .cache import CacheConfig\napp = Application(providers=[])\n"

    with pytest.raises(RegistrationError, match=re.escape("CacheConfig is already imported as .cache.CacheConfig")):
        register(source)


def test_reexported_class_from_loaded_module_is_not_a_conflict():
    source = f"from {LogProvider.__module__} import LogProvider\napp = Application(providers=[])\n"

    updated = register_provider(source, "LogProvider", "LogProvider", {"LogProvider": "fastapi_startkit.logging"})

    assert updated.count("import LogProvider") == 1
    assert "Application(providers=[LogProvider])" in updated


def test_conflicting_import_prints_manual_steps_and_leaves_bootstrap(tmp_path):
    app = make_app(tmp_path)
    bootstrap = BOOTSTRAP.replace(
        "from config.logging import LoggingConfig\n",
        "from config.logging import LoggingConfig\nfrom legacy.cache import CacheConfig\n",
    )
    (app / "bootstrap/application.py").write_text(bootstrap)

    tester = run(cache_install(tmp_path), app)

    assert tester.status_code == 1
    assert (app / "bootstrap/application.py").read_text() == bootstrap
    error = tester.io.fetch_error()
    assert "CacheConfig is already imported as legacy.cache.CacheConfig, not config.cache.CacheConfig." in error
    assert "Register CacheProvider manually:" in error
    assert "from config.cache import CacheConfig" in error


def test_edited_bootstrap_compiles(tmp_path):
    app = make_app(tmp_path)

    run(cache_install(tmp_path), app)

    compile((app / "bootstrap/application.py").read_text(), "application.py", "exec")


def test_plain_imports_bind_module_names():
    updated = register("import os\napp = Application(providers=[])\n")

    assert updated.startswith("import os\nfrom fastapi_startkit.cache import CacheProvider\n")
    with pytest.raises(RegistrationError, match=re.escape("CacheConfig is already imported as config.cache, not")):
        register("import config.cache as CacheConfig\napp = Application(providers=[])\n")
