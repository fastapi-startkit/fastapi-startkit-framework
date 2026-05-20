import unittest
from unittest.mock import MagicMock, patch
from fastapi_startkit.storage.storage import StorageManager, Storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.config = {
            "default": "local",
            "disks": {
                "local": {
                    "driver": "local",
                    "root": "/tmp/storage",
                },
                "s3": {
                    "driver": "s3",
                    "key": "aws-key",
                    "secret": "aws-secret",
                    "region": "us-east-1",
                    "bucket": "my-bucket",
                },
            },
        }
        self.storage_manager = StorageManager(self.mock_app).set_configuration(self.config)
        self.mock_driver = MagicMock()
        self.storage_manager.add_driver("local", self.mock_driver)

        # Reset Storage singleton
        Storage.instance = None

    def test_get_config_options(self):
        self.assertEqual(self.storage_manager.get_config_options("local")["root"], "/tmp/storage")
        self.assertEqual(self.storage_manager.get_config_options("default")["root"], "/tmp/storage")

    def test_disk_resolution(self):
        self.mock_driver.set_options.return_value = self.mock_driver
        driver = self.storage_manager.disk("local")
        self.assertEqual(driver, self.mock_driver)
        self.mock_driver.set_options.assert_called_with(self.config["disks"]["local"])

    @patch("fastapi_startkit.application.app")
    def test_storage_proxy_methods(self, mock_app_getter):
        mock_app_getter.return_value = self.mock_app
        self.mock_app.make.return_value = self.storage_manager

        # Mock disk() to return the mock driver
        self.mock_driver.set_options.return_value = self.mock_driver

        # Test proxying put
        Storage.put("test.txt", "content")
        self.mock_driver.put.assert_called_with("test.txt", "content")

        # Test disk selection proxy
        Storage.disk("local")
        self.mock_driver.set_options.assert_called()

    def test_storage_singleton_behavior(self):
        with patch("fastapi_startkit.application.app") as mock_app_getter:
            mock_app_getter.return_value = self.mock_app
            self.mock_app.make.return_value = self.storage_manager

            s1 = Storage.init()
            s2 = Storage.init()
            self.assertEqual(s1, s2)
            self.assertEqual(s1, self.storage_manager)

    def test_local_driver_download(self):
        from fastapi_startkit.storage.drivers.local import LocalDriver
        from fastapi.responses import FileResponse

        driver = LocalDriver(self.mock_app)
        driver.set_options({"root": "/tmp"})

        with patch("os.makedirs"):
            response = driver.download("test.txt")
            self.assertIsInstance(response, FileResponse)
            self.assertEqual(response.path, "/tmp/test.txt")

    def test_s3_driver_download(self):
        from fastapi_startkit.storage.drivers.s3 import S3Driver
        from fastapi.responses import RedirectResponse

        driver = S3Driver(self.mock_app)
        driver.set_options({"bucket": "test-bucket", "key": "key", "secret": "secret"})

        with patch.object(driver, "get_client") as mock_client_getter:
            mock_client = MagicMock()
            mock_client_getter.return_value = mock_client
            mock_client.generate_presigned_url.return_value = "https://s3.url"

            response = driver.download("test.txt")
            self.assertIsInstance(response, RedirectResponse)
            self.assertEqual(response.headers["location"], "https://s3.url")

    def test_storage_fake(self):
        with patch("fastapi_startkit.application.app") as mock_app_getter:
            mock_app_getter.return_value = self.mock_app
            self.mock_app.make.return_value = self.storage_manager

            # Fake the 's3' disk
            Storage.fake("s3")

            # The driver for 's3' should now be a LocalDriver (the fake)
            from fastapi_startkit.storage.drivers.local import LocalDriver

            driver = self.storage_manager.get_driver("s3")
            self.assertIsInstance(driver, LocalDriver)

            # Verify it uses a temporary directory
            self.assertIn("storage_fake_s3_", driver.options["root"])
