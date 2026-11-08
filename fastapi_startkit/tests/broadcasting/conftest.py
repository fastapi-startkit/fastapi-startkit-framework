import pytest

SECRET = "test-reverb-secret"


@pytest.fixture(autouse=True)
def reverb_secret(monkeypatch):
    monkeypatch.setenv("REVERB_APP_SECRET", SECRET)
    return SECRET
