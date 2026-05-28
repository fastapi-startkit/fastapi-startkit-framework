"""Tests for the S3Driver with boto3/botocore mocked (task #14)."""

from unittest.mock import MagicMock, patch

import pytest

from fastapi_startkit.storage.drivers.s3 import S3Driver


@pytest.fixture
def driver():
    app = MagicMock()
    d = S3Driver(app)
    d.set_options(
        {
            "bucket": "test-bucket",
            "key": "AWS_KEY",
            "secret": "AWS_SECRET",
            "region": "us-east-1",
        }
    )
    return d


@pytest.fixture
def mock_resource(driver):
    """Patch get_resource so S3 calls never hit AWS."""
    mock_res = MagicMock()
    with patch.object(driver, "get_resource", return_value=mock_res):
        yield mock_res


@pytest.fixture
def mock_client(driver):
    mock_cl = MagicMock()
    with patch.object(driver, "get_client", return_value=mock_cl):
        yield mock_cl


# ---------------------------------------------------------------------------
# put
# ---------------------------------------------------------------------------


class TestS3DriverPut:
    def test_put_calls_put_object_with_correct_key(self, driver, mock_resource):
        driver.put("uploads/file.txt", "content")
        mock_resource.Bucket.assert_called_with("test-bucket")
        mock_resource.Bucket().put_object.assert_called_with(Key="uploads/file.txt", Body="content")

    def test_put_returns_content(self, driver, mock_resource):
        result = driver.put("file.txt", "data")
        assert result == "data"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestS3DriverGet:
    def test_get_returns_decoded_content(self, driver, mock_resource):
        body = MagicMock()
        body.read.return_value = b"file content"
        mock_resource.Bucket().Object().get.return_value = {"Body": body}

        result = driver.get("file.txt")
        assert result == "file content"

    def test_get_returns_none_on_client_error(self, driver, mock_resource):
        class FakeClientError(Exception):
            pass

        mock_resource.Bucket().Object().get.side_effect = FakeClientError("not found")

        with patch.object(driver, "missing_file_exceptions", return_value=(FakeClientError,)):
            result = driver.get("missing.txt")
        assert result is None


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


class TestS3DriverExists:
    def test_exists_returns_true_when_object_loadable(self, driver, mock_resource):
        mock_resource.Bucket().Object().load.return_value = None
        with patch.object(driver, "missing_file_exceptions", return_value=(Exception,)):
            result = driver.exists("file.txt")
        assert result is True

    def test_exists_returns_false_on_client_error(self, driver, mock_resource):
        class FakeClientError(Exception):
            pass

        mock_resource.Bucket().Object().load.side_effect = FakeClientError("not found")
        with patch.object(driver, "missing_file_exceptions", return_value=(FakeClientError,)):
            result = driver.exists("missing.txt")
        assert result is False

    def test_missing_is_inverse_of_exists(self, driver, mock_resource):
        mock_resource.Bucket().Object().load.return_value = None
        with patch.object(driver, "missing_file_exceptions", return_value=(Exception,)):
            assert driver.missing("file.txt") is False


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestS3DriverDelete:
    def test_delete_calls_object_delete(self, driver, mock_resource):
        driver.delete("remove.txt")
        mock_resource.Object.assert_called_with("test-bucket", "remove.txt")
        mock_resource.Object().delete.assert_called_once()


# ---------------------------------------------------------------------------
# copy / move
# ---------------------------------------------------------------------------


class TestS3DriverCopyMove:
    def test_copy_calls_meta_client_copy(self, driver, mock_resource):
        driver.copy("src.txt", "dst.txt")
        expected_source = {"Bucket": "test-bucket", "Key": "src.txt"}
        mock_resource.meta.client.copy.assert_called_once_with(expected_source, "test-bucket", "dst.txt")

    def test_move_copies_then_deletes_source(self, driver, mock_resource):
        with patch.object(driver, "copy") as mock_copy, patch.object(driver, "delete") as mock_delete:
            driver.move("src.txt", "dst.txt")
            mock_copy.assert_called_once_with("src.txt", "dst.txt")
            mock_delete.assert_called_once_with("src.txt")


# ---------------------------------------------------------------------------
# download (presigned URL)
# ---------------------------------------------------------------------------


class TestS3DriverDownload:
    def test_download_returns_redirect_response(self, driver, mock_client):
        mock_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/signed-url"

        from fastapi.responses import RedirectResponse

        response = driver.download("file.txt")
        assert isinstance(response, RedirectResponse)

    def test_download_generates_presigned_url_with_correct_params(self, driver, mock_client):
        mock_client.generate_presigned_url.return_value = "https://presigned"

        driver.download("folder/file.txt")
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "folder/file.txt"},
            ExpiresIn=3600,
        )


# ---------------------------------------------------------------------------
# url helper
# ---------------------------------------------------------------------------


class TestS3DriverUrl:
    def test_url_returns_correct_format(self, driver):
        driver.set_options({**driver.options, "url": "https://cdn.example.com"})
        assert driver.url("images/photo.jpg") == "https://cdn.example.com/images/photo.jpg"


# ---------------------------------------------------------------------------
# get_bucket
# ---------------------------------------------------------------------------


class TestS3DriverGetBucket:
    def test_get_bucket_returns_configured_bucket(self, driver):
        assert driver.get_bucket() == "test-bucket"
