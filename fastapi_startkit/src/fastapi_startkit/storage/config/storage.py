from dataclasses import dataclass, field
from typing import Any, Dict

from fastapi_startkit.environment import env
from fastapi_startkit.storage import LocalDiskConfig, S3Config, PublicDiskConfig


@dataclass
class StorageConfig:
    default: str = field(default_factory=lambda: env("FILESYSTEM_DISK", "local"))

    disks: dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "local": LocalDiskConfig(
                root=env("FILESYSTEM_DISK_ROOT", "storage"),
            ),
            "public": PublicDiskConfig(
                root=env("FILESYSTEM_PUBLIC_DISK_ROOT", "storage/app/public"),
                url=env("FILESYSTEM_PUBLIC_DISK_URL", "/storage"),
            ),
            "s3": S3Config(
                key=env("AWS_ACCESS_KEY_ID", "", cast=False),
                secret=env("AWS_SECRET_ACCESS_KEY", "", cast=False),
                region=env("AWS_DEFAULT_REGION", "", cast=False),
                bucket=env("AWS_BUCKET", "", cast=False),
                url=env("AWS_URL", "", cast=False),
                endpoint=env("AWS_ENDPOINT", "", cast=False),
            ),
        }
    )
