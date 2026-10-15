from fastapi_startkit.configuration import Config
from dataclasses import dataclass, field

from fastapi_startkit.environment import env
from fastapi_startkit.storage import LocalDiskConfig, PublicDiskConfig, S3Config


@dataclass
class StorageConfig(Config):
    default: str = env("FILESYSTEM_DISK", "local")

    disks: dict[str, Config] = field(
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
                region=env("AWS_DEFAULT_REGION", "us-east-1"),
                bucket=env("AWS_BUCKET", "", cast=False),
                url=env("AWS_URL", "", cast=False),
                endpoint=env("AWS_ENDPOINT", "", cast=False),
                use_path_style_endpoint=True,
            ),
        }
    )
