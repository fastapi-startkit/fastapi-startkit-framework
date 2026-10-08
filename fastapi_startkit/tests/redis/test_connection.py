import asyncio

import pytest


async def test_command_runs_raw_command(manager, raw):
    await manager.command("rpush", ["list", "a", "b", "c"])

    assert await manager.command("lrange", ["list", 0, -1]) == ["a", "b", "c"]
    assert await manager.command("DEL", ["list"]) == 1
    assert await raw.keys("*") == []


async def test_command_without_parameters(manager):
    assert await manager.command("ping") is True


async def test_pipeline_with_sync_callback(manager, raw):
    def callback(pipe):
        for i in range(3):
            pipe.set(f"key:{i}", i)

    assert await manager.pipeline(callback) == [True, True, True]
    assert sorted(await raw.keys("*")) == ["app_key:0", "app_key:1", "app_key:2"]


async def test_pipeline_with_async_callback(manager):
    async def callback(pipe):
        pipe.set("counter", 1)
        pipe.incr("counter")

    assert await manager.pipeline(callback) == [True, 2]


async def test_pipeline_as_context_manager(manager, raw):
    async with manager.pipeline() as pipe:
        pipe.set("a", 1).set("b", 2)
        assert await pipe.execute() == [True, True]

    assert sorted(await raw.keys("*")) == ["app_a", "app_b"]


async def test_transaction_with_callback(manager):
    await manager.set("balance", 10)

    results = await manager.transaction(lambda multi: multi.decrby("balance", 3).incr("audit"))

    assert results == [7, 1]


async def test_transaction_as_context_manager(manager):
    async with manager.transaction() as multi:
        multi.incr("visits").incr("visits")
        assert await multi.execute() == [1, 2]


async def test_eval_prefixes_keys(manager, raw):
    await manager.set("name", "taylor")

    result = await manager.eval("return redis.call('get', KEYS[1]) .. ARGV[1]", 1, "name", "!")

    assert result == "taylor!"


async def wait_for_subscriber(manager, pattern=False):
    for _ in range(100):
        count = await manager.execute_command("PUBSUB", "NUMPAT") if pattern else None
        channels = await manager.execute_command("PUBSUB", "CHANNELS")
        if (pattern and count) or (not pattern and channels):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("subscriber never registered")


async def test_subscribe_receives_published_messages(manager):
    received = asyncio.Queue()
    listener = asyncio.create_task(
        manager.subscribe(["orders", "invoices"], lambda message, channel: received.put_nowait((message, channel)))
    )
    await wait_for_subscriber(manager)

    assert await manager.publish("orders", "created") == 1
    assert await asyncio.wait_for(received.get(), 1) == ("created", "orders")

    listener.cancel()
    with pytest.raises(asyncio.CancelledError):
        await listener


async def test_psubscribe_with_async_callback(manager):
    received = asyncio.Queue()

    async def callback(message, channel):
        await received.put((message, channel))

    listener = asyncio.create_task(manager.psubscribe("users.*", callback))
    await wait_for_subscriber(manager, pattern=True)

    await manager.publish("users.1", "updated")
    assert await asyncio.wait_for(received.get(), 1) == ("updated", "users.1")

    listener.cancel()
    with pytest.raises(asyncio.CancelledError):
        await listener


def test_private_attributes_are_not_proxied(manager):
    with pytest.raises(AttributeError):
        manager.connection()._missing
