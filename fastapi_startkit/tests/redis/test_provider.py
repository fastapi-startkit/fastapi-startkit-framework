import fakeredis

from fastapi_startkit.application import Application
from fastapi_startkit.configuration import config
from fastapi_startkit.facades import Redis
from fastapi_startkit.redis import RedisManager, RedisProvider

from .conftest import make_config


def make_app(tmp_path, provider=RedisProvider):
    return Application(base_path=tmp_path, env="testing", providers=[provider])


def test_binds_manager_and_merges_config(tmp_path):
    app = make_app(tmp_path)

    assert isinstance(app.make("redis"), RedisManager)
    assert config("redis.client") == "redis"
    assert config("redis.connections.cache.database") == 1


def test_user_config_overrides_defaults(tmp_path):
    app = make_app(tmp_path, (RedisProvider, lambda: make_config(prefix="shop:")))

    assert app.make("redis").config["options"] == {"prefix": "shop:"}


def test_publishes_config_stub(tmp_path):
    app = make_app(tmp_path)

    assert "config/redis.py" in app.published_resources["redis"].values()


async def test_facade_proxies_to_manager(tmp_path):
    app = make_app(tmp_path, (RedisProvider, lambda: make_config()))
    server = fakeredis.FakeServer()
    Redis.extend("fake", lambda parameters: fakeredis.FakeAsyncRedis(server=server, **parameters))

    await Redis.set("name", "taylor")
    await Redis.connection("cache").set("name", "otwell")

    assert await Redis.get("name") == "taylor"
    assert await Redis.connection("cache").get("name") == "otwell"
    assert await Redis.command("get", ["name"]) == "taylor"
    assert Redis.connection() is app.make("redis").connection()


async def test_shutdown_disconnects_connections(tmp_path):
    app = make_app(tmp_path, (RedisProvider, lambda: make_config()))
    manager = app.make("redis")
    manager.extend("fake", lambda parameters: fakeredis.FakeAsyncRedis(**parameters))
    manager.connection()

    async with app.fastapi.router.lifespan_context(app.fastapi):
        pass

    assert manager.connections() == {}


def test_boot_skips_shutdown_hook_without_fastapi(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    provider = RedisProvider(app)

    def missing_fastapi(*args, **kwargs):
        raise RuntimeError("FastAPI is not installed")

    monkeypatch.setattr(app, "add_event_handler", missing_fastapi)
    provider.boot()
