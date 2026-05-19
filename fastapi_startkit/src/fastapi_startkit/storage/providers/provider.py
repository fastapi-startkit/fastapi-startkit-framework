from pathlib import Path
from ...providers import Provider
from ..storage import StorageManager
from ...configuration import config
from ..drivers import LocalDriver, S3Driver
from ..config.storage import StorageConfig


class StorageProvider(Provider):
    def register(self):
        config_data = self.resolve_config(StorageConfig)
        self.merge_config_from(config_data, "storage")

        storage = StorageManager(self.app, config("storage"))
        storage.add_driver("local", LocalDriver(self.app))
        storage.add_driver("s3", S3Driver(self.app))
        self.app.bind("storage", storage)

    def boot(self):
        self.publishes({Path(__file__).resolve().parent.parent.joinpath("config/storage.py"): "config/storage.py"})

        if not self.app.fastapi:
            return

        # Resolve the public disk root from config so the route and the driver
        # always agree on the same absolute directory.
        public_disk = config("storage.disks.public") or {}
        public_root = public_disk.get("root", "storage/app/public")
        public_dir = Path(self.app.base_path) / public_root
        public_dir.mkdir(parents=True, exist_ok=True)

        # Serve public storage files via a plain bytes Response.
        # FileResponse / StaticFiles are streaming responses — Starlette's
        # BaseHTTPMiddleware sends an extra empty body chunk after them, which
        # breaks the Content-Length and raises RuntimeError. Reading the file
        # into memory and returning a regular Response avoids that entirely.
        import mimetypes
        from fastapi import HTTPException
        from fastapi.responses import Response

        async def serve_storage_file(path: str):
            file_path = public_dir / path
            if not file_path.exists() or not file_path.is_file():
                raise HTTPException(status_code=404)
            media_type, _ = mimetypes.guess_type(str(file_path))
            return Response(
                content=file_path.read_bytes(),
                media_type=media_type or "application/octet-stream",
            )

        self.app.fastapi.get("/storage/{path:path}", include_in_schema=False)(serve_storage_file)
