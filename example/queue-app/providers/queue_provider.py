from fastapi_startkit.environment import env
from fastapi_startkit.providers import Provider
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend


class QueueProvider(Provider):
    def register(self) -> None:
        redis_host = env("REDIS_HOST", "127.0.0.1")
        redis_port = env("REDIS_PORT", "6379")
        redis_url = f"redis://{redis_host}:{redis_port}"

        broker = ListQueueBroker(redis_url).with_result_backend(
            RedisAsyncResultBackend(redis_url)
        )

        self.app.bind("broker", broker)

    def boot(self) -> None:
        if not self.app.has("fastapi"):
            return

        fastapi_app = self.app.make("fastapi")
        broker = self.app.make("broker")

        @fastapi_app.on_event("startup")
        async def startup_broker():
            await broker.startup()

        @fastapi_app.on_event("shutdown")
        async def shutdown_broker():
            await broker.shutdown()
