from fastapi_startkit.configuration import Config
from dataclasses import dataclass, field


@dataclass
class LocalDiskConfig(Config):
    driver: str = "local"
    root: str = "storage"
    serve: bool = True
    throw: bool = False
    report: bool = False


@dataclass
class PublicDiskConfig(LocalDiskConfig):
    driver: str = "local"
    serve: bool = True
    throw: bool = False
    report: bool = False
    visibility: str = "public"
    url: str = "/storage"


@dataclass
class S3Config(Config):
    driver: str = "s3"
    key: str = ""
    secret: str = ""
    region: str = ""
    bucket: str = ""
    url: str = ""
    endpoint: str = ""
    use_path_style_endpoint: bool = False
    throw: bool = False
    report: bool = False
