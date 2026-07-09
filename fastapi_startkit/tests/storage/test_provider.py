from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from fastapi_startkit.application import Application
from fastapi_startkit.storage.providers.provider import StorageProvider
from fastapi_startkit.storage.storage import StorageManager


def make_app(tmp_path):
    return Application(base_path=tmp_path, env="testing", providers=[StorageProvider])


class TestRegister:
    def test_binds_storage_manager_with_drivers(self, tmp_path):
        app = make_app(tmp_path)
        storage = app.make("storage")
        assert isinstance(storage, StorageManager)
        assert "local" in storage.drivers
        assert "s3" in storage.drivers


class TestBootRoute:
    def test_serves_existing_public_file(self, tmp_path):
        app = make_app(tmp_path)
        public_dir = tmp_path / "storage" / "app" / "public"
        (public_dir / "hello.txt").write_text("hi there")

        client = TestClient(app.fastapi)
        response = client.get("/storage/hello.txt")

        assert response.status_code == 200
        assert response.text == "hi there"

    def test_returns_404_for_missing_file(self, tmp_path):
        app = make_app(tmp_path)
        client = TestClient(app.fastapi)
        assert client.get("/storage/nope.txt").status_code == 404

    def test_returns_404_for_directory_path(self, tmp_path):
        app = make_app(tmp_path)
        public_dir = tmp_path / "storage" / "app" / "public"
        (public_dir / "subdir").mkdir(parents=True, exist_ok=True)

        client = TestClient(app.fastapi)
        assert client.get("/storage/subdir").status_code == 404


class TestBootWithoutFastapi:
    def test_boot_returns_early_when_no_fastapi(self):
        app = MagicMock()
        app.published_resources = {}
        app.fastapi = None

        provider = StorageProvider(app)
        # Returns early on the falsy fastapi check — no route registration,
        # no mkdir. Reaching here without error exercises that branch.
        provider.boot()

        # The config stub is still published before the early return.
        assert app.published_resources != {}
