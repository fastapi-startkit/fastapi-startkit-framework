"""Integration tests for S3Driver.get_files against a real S3 API (MinIO).

These run against a live MinIO server (issue #218). They are skipped when
boto3 is not installed or no server is reachable, so the suite stays green
in environments without MinIO.

Override the target with MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY.
"""

import os
import uuid
from unittest.mock import MagicMock

import pytest

boto3 = pytest.importorskip("boto3")
import botocore.config  # noqa: E402

from fastapi_startkit.storage.drivers.s3 import S3Driver  # noqa: E402

ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9002")
ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minio")
SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minio123")

KEYS = {
    "root.txt": b"root content",
    "backups/a.dump": b"dump a",
    "backups/b.dump": b"dump b",
    "backups/nested/deep.dump": b"deep",
    "audio/x/y.mp3": b"audio bytes",
}


def _client():
    session = boto3.Session(
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
    )
    return session.client(
        "s3",
        endpoint_url=ENDPOINT,
        config=botocore.config.Config(
            s3={"addressing_style": "path"},
            connect_timeout=2,
            retries={"max_attempts": 1},
        ),
    )


def _minio_reachable():
    try:
        _client().list_buckets()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _minio_reachable(), reason=f"MinIO not reachable at {ENDPOINT}")


@pytest.fixture(scope="module")
def bucket_name():
    client = _client()
    name = f"fsk-get-files-{uuid.uuid4().hex[:12]}"
    client.create_bucket(Bucket=name)
    for key, body in KEYS.items():
        client.put_object(Bucket=name, Key=key, Body=body)

    yield name

    listing = client.list_objects_v2(Bucket=name).get("Contents", [])
    for obj in listing:
        client.delete_object(Bucket=name, Key=obj["Key"])
    client.delete_bucket(Bucket=name)


@pytest.fixture
def driver(bucket_name):
    d = S3Driver(MagicMock())
    d.set_options(
        {
            "bucket": bucket_name,
            "key": ACCESS_KEY,
            "secret": SECRET_KEY,
            "region": "us-east-1",
            "endpoint": ENDPOINT,
            "use_path_style_endpoint": True,
        }
    )
    return d


class TestGetFilesAgainstMinio:
    def test_root_listing_returns_only_root_level_files(self, driver):
        files = driver.get_files()
        assert [f.name() for f in files] == ["root.txt"]

    def test_one_level_deep_directory(self, driver):
        files = driver.get_files("backups")
        assert sorted(f.name() for f in files) == ["a.dump", "b.dump"]

    def test_trailing_slash_is_equivalent(self, driver):
        files = driver.get_files("backups/")
        assert sorted(f.name() for f in files) == ["a.dump", "b.dump"]

    def test_two_levels_deep_directory(self, driver):
        files = driver.get_files("backups/nested")
        assert [f.name() for f in files] == ["deep.dump"]

    def test_directory_containing_only_subdirectories_is_empty(self, driver):
        assert driver.get_files("audio") == []

    def test_nonexistent_directory_returns_empty_list(self, driver):
        assert driver.get_files("does-not-exist") == []

    def test_partial_name_prefix_is_not_a_directory_match(self, driver):
        assert driver.get_files("back") == []

    def test_listed_objects_point_at_the_real_keys(self, driver):
        files = driver.get_files("backups")
        keys = sorted(f.stream().key for f in files)
        assert keys == ["backups/a.dump", "backups/b.dump"]
