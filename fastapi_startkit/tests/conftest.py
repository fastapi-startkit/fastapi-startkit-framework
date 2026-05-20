import pytest
from fastapi_startkit.application import Application


@pytest.fixture(scope="session", autouse=True)
def init_app():
    Application(env="testing")
