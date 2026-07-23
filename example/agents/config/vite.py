from pydantic.dataclasses import dataclass


@dataclass
class ViteConfig:
    public_path: str = "public"
    build_directory: str = "build"
    hot_file: str = "hot"
    manifest_filename: str = "manifest.json"
    asset_url: str = ""
    static_url: str = "/build"
    mount_static: bool = True
