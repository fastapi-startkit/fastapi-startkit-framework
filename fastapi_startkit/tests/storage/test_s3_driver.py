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

    def test_get_bucket_returns_none_when_not_configured(self):
        app = MagicMock()
        d = S3Driver(app)
        d.set_options({})
        assert d.get_bucket() is None


# ---------------------------------------------------------------------------
# Edge cases: unexpected exceptions must propagate (not be swallowed)
# ---------------------------------------------------------------------------


class TestS3DriverExceptionPropagation:
    def test_get_raises_unexpected_exception(self, driver, mock_resource):
        class DatabaseError(Exception):
            pass

        mock_resource.Bucket().Object().get.side_effect = DatabaseError("unexpected")

        with patch.object(driver, "missing_file_exceptions", return_value=(FileNotFoundError,)):
            with pytest.raises(DatabaseError):
                driver.get("file.txt")

    def test_exists_raises_unexpected_exception(self, driver, mock_resource):
        class AWSDown(Exception):
            pass

        mock_resource.Bucket().Object().load.side_effect = AWSDown("service down")

        with patch.object(driver, "missing_file_exceptions", return_value=(FileNotFoundError,)):
            with pytest.raises(AWSDown):
                driver.exists("file.txt")


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------


class TestS3DriverUrlNormalization:
    def test_url_with_trailing_slash(self, driver):
        driver.set_options({**driver.options, "url": "https://cdn.example.com/"})
        assert driver.url("file.txt") == "https://cdn.example.com//file.txt"

    def test_url_without_trailing_slash(self, driver):
        driver.set_options({**driver.options, "url": "https://cdn.example.com"})
        assert driver.url("file.txt") == "https://cdn.example.com/file.txt"


# ---------------------------------------------------------------------------
# Empty and binary content
# ---------------------------------------------------------------------------


class TestS3DriverContentTypes:
    def test_put_empty_content(self, driver, mock_resource):
        driver.put("empty.txt", "")
        mock_resource.Bucket().put_object.assert_called_with(Key="empty.txt", Body="")

    def test_put_binary_content(self, driver, mock_resource):
        content = b"\x00\x01\x02"
        driver.put("binary.bin", content)
        mock_resource.Bucket().put_object.assert_called_with(Key="binary.bin", Body=content)


# ---------------------------------------------------------------------------
# Move atomicity: copy failure must not delete source
# ---------------------------------------------------------------------------


class TestS3DriverMoveAtomicity:
    def test_move_does_not_delete_source_when_copy_fails(self, driver):
        with (
            patch.object(driver, "copy", side_effect=Exception("copy failed")),
            patch.object(driver, "delete") as mock_delete,
        ):
            with pytest.raises(Exception, match="copy failed"):
                driver.move("src.txt", "dst.txt")
            mock_delete.assert_not_called()


# ---------------------------------------------------------------------------
# Connection caching
# ---------------------------------------------------------------------------


class TestS3DriverConnectionCaching:
    def test_get_connection_returns_same_session(self):
        mock_boto3 = MagicMock()
        app = MagicMock()
        d = S3Driver(app)
        d.set_options({"key": "k", "secret": "s", "region": "us-east-1"})

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            c1 = d.get_connection()
            c2 = d.get_connection()
            assert c1 is c2
            mock_boto3.Session.assert_called_once()
