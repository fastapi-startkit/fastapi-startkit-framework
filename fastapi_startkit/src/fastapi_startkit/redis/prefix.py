from collections.abc import Callable, Sequence
from typing import Any

Positions = Callable[[Sequence[Any]], Sequence[int]]


def first(params: Sequence[Any]) -> range:
    return range(min(1, len(params)))


def second(params: Sequence[Any]) -> range:
    return range(1, min(2, len(params)))


def first_two(params: Sequence[Any]) -> range:
    return range(min(2, len(params)))


def every(params: Sequence[Any]) -> range:
    return range(len(params))


def all_but_last(params: Sequence[Any]) -> range:
    return range(len(params) - 1)


def all_but_first(params: Sequence[Any]) -> range:
    return range(1, len(params))


def interleaved(params: Sequence[Any]) -> range:
    return range(0, len(params), 2)


def numkeys_first(params: Sequence[Any]) -> range:
    return range(1, 1 + int(params[0]))


def numkeys_second(params: Sequence[Any]) -> range:
    return range(2, 2 + int(params[1]))


def destination_then_numkeys(params: Sequence[Any]) -> list[int]:
    return [0, *numkeys_second(params)]


def streams(params: Sequence[Any]) -> range:
    markers = [index for index, param in enumerate(params) if command_name(param) == "streams"]
    if not markers:
        return range(0)
    start = markers[-1] + 1
    return range(start, start + (len(params) - start) // 2)


SUBCOMMANDS = [
    "memory usage",
    "object encoding",
    "object freq",
    "object idletime",
    "object refcount",
    "xgroup create",
    "xgroup createconsumer",
    "xgroup delconsumer",
    "xgroup destroy",
    "xgroup setid",
    "xinfo consumers",
    "xinfo groups",
    "xinfo stream",
]

STRATEGIES: dict[Positions, Sequence[str]] = {
    first: """
        append bitcount bitfield bitfield_ro bitpos decr decrby dump expire expireat expiretime geoadd
        geodist geohash geopos georadius georadiusbymember geosearch get getbit getdel getex getrange getset
        hdel hexists hexpire hexpireat hexpiretime hget hgetall hgetdel hgetex hincrby hincrbyfloat hkeys
        hlen hmget hmset hpersist hpexpire hpexpireat hpexpiretime hpttl hrandfield hscan hset hsetex hsetnx
        hstrlen httl hvals incr incrby incrbyfloat keys lindex linsert llen lpop lpos lpush lpushx lrange
        lrem lset ltrim move persist pexpire pexpireat pexpiretime pfadd psetex pttl restore rpop rpush
        rpushx sadd scard set setbit setex setnx setrange sismember smembers smismember sort sort_ro spop
        srandmember srem sscan strlen substr ttl type xack xadd xautoclaim xclaim xdel xlen xpending xrange
        xrevrange xsetid xtrim zadd zcard zcount zincrby zlexcount zmscore zpopmax zpopmin zrandmember
        zrange zrangebylex zrangebyscore zrank zrem zremrangebylex zremrangebyrank zremrangebyscore
        zrevrange zrevrangebylex zrevrangebyscore zrevrank zscan zscore
    """.split()
    + SUBCOMMANDS,
    second: "memory object xgroup xinfo".split(),
    first_two: "blmove brpoplpush copy geosearchstore lcs lmove rename renamenx rpoplpush smove zrangestore".split(),
    every: """
        del exists mget pfcount pfmerge sdiff sdiffstore sinter sinterstore sunion sunionstore touch unlink
        watch
    """.split(),
    all_but_last: "blpop brpop bzpopmax bzpopmin".split(),
    all_but_first: "bitop".split(),
    interleaved: "mset msetnx".split(),
    numkeys_first: "lmpop sintercard zdiff zinter zintercard zmpop zunion".split(),
    numkeys_second: "blmpop bzmpop eval eval_ro evalsha evalsha_ro fcall fcall_ro".split(),
    destination_then_numkeys: "zdiffstore zinterstore zunionstore".split(),
    streams: "xread xreadgroup".split(),
}

KEY_POSITIONS: dict[str, Positions] = {
    command: strategy for strategy, commands in STRATEGIES.items() for command in commands
}


def command_name(command: Any) -> str:
    if isinstance(command, (bytes, bytearray, memoryview)):
        return bytes(command).decode(errors="replace").lower()
    return str(command).lower()


def prefix_key(prefix: str, key: Any) -> Any:
    if isinstance(key, bytes):
        return prefix.encode() + key
    return f"{prefix}{key}"


def prefix_command(prefix: str, args: Sequence[Any]) -> tuple[Any, ...]:
    if not args:
        return tuple(args)

    command, *params = args
    strategy = KEY_POSITIONS.get(command_name(command))
    if strategy is None:
        return tuple(args)

    positions = set(strategy(params))
    return (
        command,
        *(prefix_key(prefix, param) if index in positions else param for index, param in enumerate(params)),
    )


def apply_prefix[T](target: T, prefix: str) -> T:
    if not prefix:
        return target

    execute_command = getattr(target, "execute_command")

    def prefixed_execute_command(*args: Any, **options: Any) -> Any:
        return execute_command(*prefix_command(prefix, args), **options)

    setattr(target, "execute_command", prefixed_execute_command)
    return target
