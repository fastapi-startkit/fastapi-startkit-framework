import pytest

from fastapi_startkit.redis.prefix import apply_prefix, prefix_command


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("GET", "a"), ("GET", "p:a")),
        (("SET", "a", "1", "EX", 10), ("SET", "p:a", "1", "EX", 10)),
        (("DEL", "a", "b"), ("DEL", "p:a", "p:b")),
        (("RENAME", "a", "b"), ("RENAME", "p:a", "p:b")),
        (("BLPOP", "a", "b", 5), ("BLPOP", "p:a", "p:b", 5)),
        (("BITOP", "AND", "dest", "a"), ("BITOP", "AND", "p:dest", "p:a")),
        (("MSET", "a", 1, "b", 2), ("MSET", "p:a", 1, "p:b", 2)),
        (("ZUNION", 2, "a", "b", "WITHSCORES"), ("ZUNION", 2, "p:a", "p:b", "WITHSCORES")),
        (("EVAL", "script", 1, "a", "arg"), ("EVAL", "script", 1, "p:a", "arg")),
        (("ZINTERSTORE", "dest", 2, "a", "b"), ("ZINTERSTORE", "p:dest", 2, "p:a", "p:b")),
        (("PUBLISH", "chan", "hi"), ("PUBLISH", "chan", "hi")),
        (("PING",), ("PING",)),
        ((), ()),
    ],
)
def test_prefixes_key_positions(args, expected):
    assert prefix_command("p:", args) == expected


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            ("XREAD", "COUNT", 1, "STREAMS", "a", "b", "0", "0"),
            ("XREAD", "COUNT", 1, "STREAMS", "p:a", "p:b", "0", "0"),
        ),
        (
            ("XREADGROUP", "GROUP", "g", "c", b"STREAMS", "a", ">"),
            ("XREADGROUP", "GROUP", "g", "c", b"STREAMS", "p:a", ">"),
        ),
        (("XREAD", "COUNT", 1), ("XREAD", "COUNT", 1)),
        (("XREAD", "STREAMS", "a", "streams", "0", "0"), ("XREAD", "STREAMS", "p:a", "p:streams", "0", "0")),
        (("XREAD", "BLOCK", 0, "STREAMS", "streams", "$"), ("XREAD", "BLOCK", 0, "STREAMS", "p:streams", "$")),
        (
            ("XREADGROUP", "GROUP", "streams", "c", "COUNT", 5, "BLOCK", 10, "NOACK", "STREAMS", "a", "b", ">", ">"),
            (
                "XREADGROUP",
                "GROUP",
                "streams",
                "c",
                "COUNT",
                5,
                "BLOCK",
                10,
                "NOACK",
                "STREAMS",
                "p:a",
                "p:b",
                ">",
                ">",
            ),
        ),
        (
            ("XREADGROUP", "GROUP", "g", "c", "CLAIM", 100, "STREAMS", "a", ">"),
            ("XREADGROUP", "GROUP", "g", "c", "CLAIM", 100, "STREAMS", "p:a", ">"),
        ),
        (("XREAD", "UNKNOWN", "STREAMS", "a", "0"), ("XREAD", "UNKNOWN", "STREAMS", "a", "0")),
        (("XGROUP CREATE", "s", "g", "0"), ("XGROUP CREATE", "p:s", "g", "0")),
        (("XGROUP", "CREATE", "s", "g", "0"), ("XGROUP", "CREATE", "p:s", "g", "0")),
        (("XGROUP", "HELP"), ("XGROUP", "HELP")),
        (("XINFO STREAM", "s"), ("XINFO STREAM", "p:s")),
        (("MEMORY USAGE", "k"), ("MEMORY USAGE", "p:k")),
        (("HTTL", "h", "FIELDS", 1, "f"), ("HTTL", "p:h", "FIELDS", 1, "f")),
        (("SUBSTR", "k", 0, 1), ("SUBSTR", "p:k", 0, 1)),
        ((b"GET", "a"), (b"GET", "p:a")),
    ],
)
def test_prefixes_streams_and_subcommands(args, expected):
    assert prefix_command("p:", args) == expected


def test_prefixes_bytes_and_non_string_keys():
    assert prefix_command("p:", ("GET", b"a")) == ("GET", b"p:a")
    assert prefix_command("p:", ("GET", 7)) == ("GET", "p:7")


def test_command_lookup_is_case_insensitive():
    assert prefix_command("p:", ("get", "a")) == ("get", "p:a")


def test_empty_prefix_leaves_target_untouched():
    class Target:
        def execute_command(self, *args):
            return args

    target = Target()
    assert apply_prefix(target, "") is target
    assert target.execute_command("GET", "a") == ("GET", "a")


def test_apply_prefix_wraps_execute_command():
    class Target:
        def execute_command(self, *args, **options):
            return args, options

    target = apply_prefix(Target(), "p:")
    assert target.execute_command("GET", "a", keys=["a"]) == (("GET", "p:a"), {"keys": ["a"]})
