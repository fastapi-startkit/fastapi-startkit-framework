import fakeredis
import pytest

from fastapi_startkit.redis import RedisManager


def make_config(prefix="app_", **overrides):
    config = {
        "client": "fake",
        "options": {"prefix": prefix},
        "connections": {
            "default": {"host": "127.0.0.1", "port": 6379, "database": 0},
            "cache": {"host": "127.0.0.1", "port": 6379, "database": 1},
        },
    }
    config.update(overrides)
    return config


@pytest.fixture
def server():
    return fakeredis.FakeServer()


@pytest.fixture
def raw(server):
    return fakeredis.FakeAsyncRedis(server=server, decode_responses=True)


@pytest.fixture
def factory(server):
    def create(parameters):
        return fakeredis.FakeAsyncRedis(server=server, **parameters)

    return create


@pytest.fixture
def manager(factory):
    return RedisManager(make_config()).extend("fake", factory)
