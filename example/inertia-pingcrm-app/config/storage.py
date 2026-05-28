from dataclasses import dataclass, field
from typing import Any, Dict

from fastapi_startkit.environment import env
from fastapi_startkit.storage import LocalDiskConfig, PublicDiskConfig, S3Config


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
                key=env("AWS_ACCESS_KEY_ID"),
                secret=env("AWS_SECRET_ACCESS_KEY"),
                region=env("AWS_DEFAULT_REGION", "us-east-1"),
                bucket=env("AWS_BUCKET"),
                url=env("AWS_URL"),
                endpoint=env("AWS_ENDPOINT"),
                use_path_style_endpoint=True,
            ),
        }
    )
