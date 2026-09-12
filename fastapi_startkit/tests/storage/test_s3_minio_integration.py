"""Real S3 integration tests for get_files, run against a local MinIO (issue #218).

Skipped unless a MinIO endpoint is reachable. Point the suite at a different
instance with S3_TEST_ENDPOINT / S3_TEST_KEY / S3_TEST_SECRET.
"""

import os
import socket
from unittest.mock import MagicMock
from urllib.parse import urlparse

import pytest

from fastapi_startkit.storage.drivers.s3 import S3Driver

ENDPOINT = os.getenv("S3_TEST_ENDPOINT", "http://127.0.0.1:9002")
KEY = os.getenv("S3_TEST_KEY", "minio")
SECRET = os.getenv("S3_TEST_SECRET", "minio123")
BUCKET = os.getenv("S3_TEST_BUCKET", "fsk-get-files-test")

pytest.importorskip("boto3", reason="boto3 is required for the S3 integration tests")


def _endpoint_is_reachable():
    url = urlparse(ENDPOINT)
    try:
        with socket.create_connection((url.hostname, url.port or 80), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _endpoint_is_reachable(),
    reason=f"no S3-compatible endpoint at {ENDPOINT} — start MinIO to run these",
)

LAYOUT = {
    "root.txt": b"root content",
    "backups/a.sql": b"a content",
    "backups/b.sql": b"b content",
    "backups/2024/deep.sql": b"deep content",
    "audio/x/y.mp3": b"nested only",
}


@pytest.fixture(scope="module")
def driver():
    d = S3Driver(MagicMock())
    d.set_options(
        {
            "bucket": BUCKET,
            "key": KEY,
            "secret": SECRET,
            "region": "us-east-1",
            "endpoint": ENDPOINT,
            "use_path_style_endpoint": True,
        }
    )

    bucket = d.get_resource().Bucket(BUCKET)
    if bucket.creation_date is None:
        bucket.create()
    bucket.objects.all().delete()

    for key, body in LAYOUT.items():
        bucket.put_object(Key=key, Body=body)

    yield d

    bucket.objects.all().delete()


class TestS3GetFilesAgainstMinio:
    def test_lists_files_directly_under_the_prefix(self, driver):
        assert [f.name() for f in driver.get_files("backups")] == ["a.sql", "b.sql"]

    def test_nested_keys_are_excluded(self, driver):
        assert driver.get_files("audio") == []

    def test_deeper_keys_do_not_leak_into_the_listing(self, driver):
        assert "deep.sql" not in [f.name() for f in driver.get_files("backups")]

    def test_root_level_keys_do_not_leak_into_a_prefixed_listing(self, driver):
        assert "root.txt" not in [f.name() for f in driver.get_files("backups")]

    def test_trailing_slash_is_tolerated(self, driver):
        assert [f.name() for f in driver.get_files("backups/")] == [f.name() for f in driver.get_files("backups")]

    def test_no_directory_lists_the_root_only(self, driver):
        assert [f.name() for f in driver.get_files()] == ["root.txt"]

    def test_nested_prefix_is_listable(self, driver):
        assert [f.name() for f in driver.get_files("backups/2024")] == ["deep.sql"]

    def test_unknown_directory_returns_empty_list(self, driver):
        assert driver.get_files("nope") == []

    def test_listed_objects_resolve_back_to_their_content(self, driver):
        for file in driver.get_files("backups"):
            assert driver.get(f"backups/{file.name()}") == LAYOUT[f"backups/{file.name()}"].decode()
