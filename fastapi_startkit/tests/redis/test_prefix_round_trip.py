import fakeredis
import pytest

from fastapi_startkit.redis import Connection


async def test_xadd_then_xread(manager, raw):
    entry = await manager.xadd("stream", {"a": "1"})

    assert await raw.keys("*") == ["app_stream"]
    assert await manager.xread({"stream": "0"}) == [["app_stream", [(entry, {"a": "1"})]]]


async def test_xread_with_count_and_multiple_streams(manager):
    await manager.xadd("one", {"a": "1"})
    await manager.xadd("two", {"b": "2"})

    result = await manager.xread({"one": "0", "two": "0"}, count=1)

    assert [stream for stream, _ in result] == ["app_one", "app_two"]


async def test_xgroup_create_and_xreadgroup(manager):
    entry = await manager.xadd("jobs", {"job": "send"})

    assert await manager.xgroup_create("jobs", "workers", id="0") is True
    result = await manager.xreadgroup("workers", "worker-1", {"jobs": ">"})

    assert result == [["app_jobs", [(entry, {"job": "send"})]]]
    assert await manager.xack("jobs", "workers", entry) == 1


async def test_xgroup_create_with_mkstream_and_destroy(manager, raw):
    assert await manager.xgroup_create("events", "workers", mkstream=True) is True
    assert await raw.exists("app_events") == 1
    assert await manager.xgroup_destroy("events", "workers") == 1


async def test_xgroup_consumer_commands(manager):
    await manager.xgroup_create("events", "workers", mkstream=True)

    assert await manager.xgroup_createconsumer("events", "workers", "worker-1") == 1
    assert await manager.xgroup_delconsumer("events", "workers", "worker-1") == 0


async def test_xgroup_setid(manager):
    await manager.xadd("events", {"a": "1"})
    await manager.xgroup_create("events", "workers", id="0")

    assert await manager.xgroup_setid("events", "workers", "$") is True


async def test_xinfo_stream_and_groups(manager):
    await manager.xadd("events", {"a": "1"})
    await manager.xgroup_create("events", "workers", id="0")

    assert (await manager.xinfo_stream("events"))["length"] == 1
    assert [group["name"] for group in await manager.xinfo_groups("events")] == ["workers"]
    assert await manager.xinfo_consumers("events", "workers") == []


async def test_raw_split_subcommand_form(manager):
    await manager.command("xadd", ["events", "*", "a", "1"])

    assert await manager.command("xgroup", ["create", "events", "workers", "0"]) == "OK"
    assert await manager.command("xgroup", ["destroy", "events", "workers"]) == 1


async def test_hash_field_expiration(manager):
    await manager.hset("hash", mapping={"field": "value", "other": "value"})

    assert await manager.hexpire("hash", 100, "field") == [1]
    assert 0 < (await manager.httl("hash", "field"))[0] <= 100
    assert 0 < (await manager.hpttl("hash", "field"))[0] <= 100_000
    assert (await manager.hexpiretime("hash", "field"))[0] > 0
    assert (await manager.hpexpiretime("hash", "field"))[0] > 0
    assert await manager.hpersist("hash", "field") == [1]
    assert await manager.httl("hash", "field") == [-1]

    assert await manager.hpexpire("hash", 100_000, "other") == [1]
    assert await manager.hexpireat("hash", 4_000_000_000, "other") == [1]
    assert await manager.hpexpireat("hash", 4_000_000_000_000, "other") == [1]
    assert (await manager.httl("hash", "other"))[0] > 100


async def test_substr(manager):
    await manager.set("greeting", "hello world")

    assert await manager.command("substr", ["greeting", 0, 4]) == "hello"


async def recorded(client_method):
    sent = []

    async def record(*args, **options):
        sent.append(args)

    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    client.execute_command = record
    await client_method(Connection(client, "default", "app_"))
    return sent


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda c: c.memory_usage("counter"), ("MEMORY USAGE", "app_counter")),
        (lambda c: c.object("encoding", "counter"), ("OBJECT", "encoding", "app_counter")),
        (lambda c: c.command("object", ["freq", "counter"]), ("OBJECT", "freq", "app_counter")),
        (lambda c: c.command("xsetid", ["events", "5-0"]), ("XSETID", "app_events", "5-0")),
        (lambda c: c.xinfo_consumers("events", "workers"), ("XINFO CONSUMERS", "app_events", "workers")),
        (lambda c: c.command("memory", ["stats"]), ("MEMORY", "stats")),
    ],
)
async def test_commands_unsupported_by_fakeredis_send_prefixed_keys(call, expected):
    assert await recorded(call) == [expected]
