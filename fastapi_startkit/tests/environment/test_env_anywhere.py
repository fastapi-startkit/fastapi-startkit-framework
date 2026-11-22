from collections import OrderedDict, defaultdict, namedtuple
from dataclasses import dataclass, field

from fastapi_startkit.ai import AIConfig, BedrockConfig, GoogleConfig
from fastapi_startkit.ai.providers.ai_provider import AIProvider
from fastapi_startkit.application import Application
from fastapi_startkit.configuration import Configuration
from fastapi_startkit.environment import env, resolve
from fastapi_startkit.support.config import Config


def test_env_inside_default_factory_dict(monkeypatch):
    @dataclass
    class Settings(Config):
        models: dict[str, str] = field(default_factory=lambda: {"default": env("ANYWHERE_MODEL", "fallback")})

    monkeypatch.setenv("ANYWHERE_MODEL", "from-env")
    assert Settings().models == {"default": "from-env"}
    monkeypatch.delenv("ANYWHERE_MODEL")
    assert Settings().models == {"default": "fallback"}


def test_env_inside_nested_config_objects(monkeypatch):
    @dataclass
    class Inner(Config):
        models: dict[str, str] = field(default_factory=dict)

    @dataclass
    class Outer(Config):
        inner: Inner = field(default_factory=lambda: Inner(models={"default": env("ANYWHERE_MODEL", "fallback")}))

    monkeypatch.setenv("ANYWHERE_MODEL", "from-env")
    assert Outer().inner.models["default"] == "from-env"


def test_env_inside_constructor_arguments(monkeypatch):
    monkeypatch.setenv("ANYWHERE_MODEL", "from-env")
    config = GoogleConfig(models={"default": env("ANYWHERE_MODEL", "fallback")})
    assert config.models["default"] == "from-env"


def test_env_inside_lists_and_tuples(monkeypatch):
    @dataclass
    class Settings(Config):
        hosts: list[object] = field(
            default_factory=lambda: [env("ANYWHERE_HOST", "localhost"), {"port": env("ANYWHERE_PORT", 80)}]
        )
        pair: tuple[object, ...] = field(default_factory=lambda: (env("ANYWHERE_HOST", "localhost"),))

    monkeypatch.setenv("ANYWHERE_HOST", "db")
    monkeypatch.setenv("ANYWHERE_PORT", "5432")
    settings = Settings()
    assert settings.hosts == ["db", {"port": 5432}]
    assert settings.pair == ("db",)


def test_typed_defaults_inside_containers(monkeypatch):
    @dataclass
    class Settings(Config):
        options: dict[str, object] = field(
            default_factory=lambda: {
                "port": env("ANYWHERE_PORT", 80),
                "debug": env("ANYWHERE_DEBUG", False),
                "name": env("ANYWHERE_NAME", "app"),
            }
        )

    monkeypatch.setenv("ANYWHERE_PORT", "8080")
    monkeypatch.setenv("ANYWHERE_DEBUG", "true")
    options = Settings().options
    assert options == {"port": 8080, "debug": True, "name": "app"}
    assert type(options["port"]) is int
    assert type(options["debug"]) is bool


def test_config_store_returns_plain_resolved_values(monkeypatch):
    @dataclass
    class Settings:
        models: dict[str, object] = field(
            default_factory=lambda: {"default": env("ANYWHERE_MODEL", "fallback"), "port": env("ANYWHERE_PORT", 1)}
        )

    monkeypatch.setenv("ANYWHERE_MODEL", "from-env")
    monkeypatch.setenv("ANYWHERE_PORT", "9")
    configuration = Configuration(None)
    configuration.set("service", Settings())
    assert configuration.get("service.models.default") == "from-env"
    assert configuration.get("service.models.port") == 9

    configuration.set("raw", {"items": [env("ANYWHERE_MODEL", "fallback")]})
    assert configuration.get("raw.items") == ["from-env"]


def test_ai_provider_exposes_resolved_bedrock_model(tmp_path, monkeypatch):
    @dataclass
    class AnywhereAIConfig(AIConfig):
        providers: dict[str, Config] = field(
            default_factory=lambda: {
                "bedrock": BedrockConfig(
                    models={"default": env("ANYWHERE_BEDROCK_MODEL", "global.anthropic.claude-sonnet-5-5")}
                )
            }
        )

    monkeypatch.setenv("ANYWHERE_BEDROCK_MODEL", "restore-marker")
    monkeypatch.delenv("ANYWHERE_BEDROCK_MODEL")
    (tmp_path / ".env").write_text("ANYWHERE_BEDROCK_MODEL=from-dotenv\n")
    application = Application(base_path=tmp_path, providers=[(AIProvider, AnywhereAIConfig)])
    model = application.make("config").get("ai.providers.bedrock.models.default")
    assert model == "from-dotenv"
    assert type(model) is str


def test_ai_provider_applies_default_when_variable_is_unset(tmp_path, monkeypatch):
    @dataclass
    class AnywhereAIConfig(AIConfig):
        providers: dict[str, Config] = field(
            default_factory=lambda: {
                "bedrock": BedrockConfig(
                    models={"default": env("ANYWHERE_BEDROCK_MODEL", "global.anthropic.claude-sonnet-5-5")}
                )
            }
        )

    monkeypatch.delenv("ANYWHERE_BEDROCK_MODEL", raising=False)
    application = Application(base_path=tmp_path, providers=[(AIProvider, AnywhereAIConfig)])
    assert application.make("config").get("ai.providers.bedrock.models.default") == "global.anthropic.claude-sonnet-5-5"


def test_env_is_read_at_construction_not_import(monkeypatch):
    @dataclass
    class Settings(Config):
        models: dict[str, str] = field(default_factory=lambda: {"default": env("ANYWHERE_MODEL", "fallback")})

    monkeypatch.setenv("ANYWHERE_MODEL", "first")
    first = Settings()
    monkeypatch.setenv("ANYWHERE_MODEL", "second")
    second = Settings()
    assert first.models["default"] == "first"
    assert second.models["default"] == "second"


Endpoint = namedtuple("Endpoint", ["host", "port"])


def test_resolve_preserves_container_subclasses(monkeypatch):
    monkeypatch.setenv("ANYWHERE_HOST", "db")
    counts = defaultdict(int, {"host": env("ANYWHERE_HOST", "localhost")})
    ordered = OrderedDict(host=env("ANYWHERE_HOST", "localhost"))
    endpoint = Endpoint(env("ANYWHERE_HOST", "localhost"), 80)

    resolved_counts = resolve(counts)
    assert type(resolved_counts) is defaultdict
    assert resolved_counts.default_factory is int
    assert resolved_counts["host"] == "db"
    assert type(resolve(ordered)) is OrderedDict
    assert resolve(ordered)["host"] == "db"
    assert resolve(endpoint) == Endpoint("db", 80)
    assert type(resolve(endpoint)) is Endpoint


def test_resolve_returns_original_when_nothing_to_resolve():
    plain = {"hosts": ["db"], "pair": (1, 2)}
    assert resolve(plain) is plain


def test_class_level_access_returns_resolved_container(monkeypatch):
    @dataclass
    class Settings(Config):
        models: dict[str, str] = field(default_factory=lambda: {"default": env("ANYWHERE_MODEL", "fallback")})

    monkeypatch.setenv("ANYWHERE_MODEL", "from-env")
    assert Settings.models == {"default": "from-env"}


def test_field_without_default_and_init_disabled_may_stay_unassigned():
    @dataclass
    class Settings(Config):
        name: str = "app"
        computed: str = field(init=False)

    settings = Settings()
    assert settings.name == "app"
    assert not hasattr(settings, "computed")
