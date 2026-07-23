from typing import TYPE_CHECKING

from fastapi_startkit.exceptions.exceptions import DriverNotFound

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory


class DatabaseManager:
    def __init__(self, factory: "ConnectionFactory", config: dict):
        self.factory = factory
        self.config = config
        self.connections = {}
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate every configured connection up front so a bad config fails
        loudly at app-boot/provider-registration time, instead of lazily on
        first use (e.g. db:migrate or the first query)."""
        from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory

        for name, conn_config in self.config.get("connections", {}).items():
            if conn_config.get("url"):
                # An explicit url bypasses driver/host/port assembly entirely at
                # connection time too (see ConnectionFactory.build_url()), so it
                # is exempt from the checks below.
                continue

            driver = conn_config.get("driver")
            if not driver:
                raise DriverNotFound(
                    f"Connection '{name}' is missing a required 'driver' key. "
                    f"Supported drivers are: {', '.join(sorted(ConnectionFactory.DRIVER_URLS))}."
                )

            if driver not in ConnectionFactory.DRIVER_URLS:
                raise DriverNotFound(
                    f"Connection '{name}' has an unsupported driver {driver!r}. "
                    f"Supported drivers are: {', '.join(sorted(ConnectionFactory.DRIVER_URLS))}."
                )

            if driver == "sqlite":
                continue

            port = conn_config.get("port")
            if port not in (None, ""):
                try:
                    int(port)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Connection '{name}' has an invalid 'port' value {port!r}; expected a number."
                    ) from None

    def connection(self, name: str | None = None):
        name = self.get_default_connection_name(name)
        assert name is not None
        config = self.config.get("connections", {}).get(name)

        if config is None:
            raise ValueError(f"Connection '{name}' not found in configuration")

        if name not in self.connections:
            self.connections[name] = self.factory.make(config, name)

        return self.connections[name]

    def disconnect(self):
        pass

    def reconnect(self):
        pass

    def get_default_connection_name(self, name: str | None) -> str:
        if name is None or name == "default":
            return self.config.get("default", "default")
        return name

    def get_schema_builder(self):
        from fastapi_startkit.masoniteorm.schema import Schema

        return Schema(self)

    async def clear(self):
        for conn in self.connections.values():
            await conn.close()
            await conn.engine.dispose()
        self.connections.clear()
