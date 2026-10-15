from fastapi_startkit.redis import RedisConnectionConfig
from fastapi_startkit.support import Provider
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend


class QueueProvider(Provider):
    def register(self) -> None:
        redis = RedisConnectionConfig()
        redis_url = f"redis://{redis.host}:{redis.port}"

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
