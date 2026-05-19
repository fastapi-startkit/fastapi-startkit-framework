from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi_startkit import Application


class StorageManager:
    """File storage manager handling managing files with different drivers."""

    def __init__(self, application: "Application", store_config: dict = None):
        self.application = application
        self.drivers = {}
        self.store_config = store_config or {}
        self.options = {}

    def add_driver(self, name: str, driver: Any):
        self.drivers.update({name: driver})

    def set_configuration(self, config: dict) -> "StorageManager":
        self.store_config = config
        return self

    def get_driver(self, name: str = None) -> Any:
        if name is None:
            name = self.store_config.get("default")

        driver_name = self.get_config_options(name).get("driver")
        return self.drivers[driver_name]

    def get_config_options(self, name: str = None) -> dict:
        disks = self.store_config.get("disks", {})
        if name is None or name == "default":
            name = self.store_config.get("default")

        return disks.get(name, {})

    def disk(self, name: str = "default") -> Any:
        """Get the file manager instance for the given disk name."""
        if name == "default":
            name = self.store_config.get("default")

        store_config = self.get_config_options(name)
        driver = self.get_driver(name)
        return driver.set_options(store_config)

    def fake(self, name: str = "default") -> "FakeDriver":
        """
        Replace the named disk with a FakeDriver backed by a temp directory.

        The fake uses a plain LocalDriver under the hood (same as Laravel) so
        all normal storage operations work, and the returned object exposes
        assertion helpers (assertExists, assertMissing, assertCount, …).

        The driver name key that the disk config references (e.g. "s3") is
        replaced in self.drivers so that any subsequent Storage.disk(name)
        call transparently returns the fake.
        """
        if name == "default":
            name = self.store_config.get("default", "local")

        from .drivers.fake import FakeDriver

        fake = FakeDriver(self.application, disk_name=name)

        # Resolve which driver key this disk uses (e.g. "s3", "local") and
        # replace that slot so get_driver() picks up the fake transparently.
        driver_key = self.get_config_options(name).get("driver", name)
        self.drivers[driver_key] = fake

        return fake

    def put(self, *args, **kwargs):
        return self.disk().put(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.disk().get(*args, **kwargs)

    def exists(self, *args, **kwargs):
        return self.disk().exists(*args, **kwargs)

    def missing(self, *args, **kwargs):
        return self.disk().missing(*args, **kwargs)

    def stream(self, *args, **kwargs):
        return self.disk().stream(*args, **kwargs)

    def copy(self, *args, **kwargs):
        return self.disk().copy(*args, **kwargs)

    def move(self, *args, **kwargs):
        return self.disk().move(*args, **kwargs)

    def prepend(self, *args, **kwargs):
        return self.disk().prepend(*args, **kwargs)

    def append(self, *args, **kwargs):
        return self.disk().append(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.disk().delete(*args, **kwargs)

    def store(self, *args, **kwargs):
        return self.disk().store(*args, **kwargs)

    def download(self, *args, **kwargs):
        return self.disk().download(*args, **kwargs)

    def url(self, *args, **kwargs):
        return self.disk().url(*args, **kwargs)


class Storage:
    instance = None

    def __init__(self):
        from fastapi_startkit.application import app

        self.app = app()
        self.storage: StorageManager = self.app.make("storage")

    @classmethod
    def init(cls) -> StorageManager:
        if cls.instance:
            return cls.instance.storage
        cls.instance = Storage()
        return cls.instance.storage

    @classmethod
    def disk(cls, name="default"):
        return cls.init().disk(name)

    @classmethod
    def fake(cls, name="default"):
        return cls.init().fake(name)

    @classmethod
    def put(cls, *args, **kwargs):
        return cls.init().put(*args, **kwargs)

    @classmethod
    def get(cls, *args, **kwargs):
        return cls.init().get(*args, **kwargs)

    @classmethod
    def exists(cls, *args, **kwargs):
        return cls.init().exists(*args, **kwargs)

    @classmethod
    def missing(cls, *args, **kwargs):
        return cls.init().missing(*args, **kwargs)

    @classmethod
    def stream(cls, *args, **kwargs):
        return cls.init().stream(*args, **kwargs)

    @classmethod
    def copy(cls, *args, **kwargs):
        return cls.init().copy(*args, **kwargs)

    @classmethod
    def move(cls, *args, **kwargs):
        return cls.init().move(*args, **kwargs)

    @classmethod
    def prepend(cls, *args, **kwargs):
        return cls.init().prepend(*args, **kwargs)

    @classmethod
    def append(cls, *args, **kwargs):
        return cls.init().append(*args, **kwargs)

    @classmethod
    def delete(cls, *args, **kwargs):
        return cls.init().delete(*args, **kwargs)

    @classmethod
    def store(cls, *args, **kwargs):
        return cls.init().store(*args, **kwargs)

    @classmethod
    def download(cls, *args, **kwargs):
        return cls.init().download(*args, **kwargs)

    @classmethod
    def url(cls, *args, **kwargs):
        return cls.init().url(*args, **kwargs)
