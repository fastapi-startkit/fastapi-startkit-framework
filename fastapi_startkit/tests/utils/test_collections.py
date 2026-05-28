"""Tests for Collection utility class (task #15)."""

import pytest

from fastapi_startkit.utils.collections import Collection, collect, flatten


class TestCollectionBasics:
    def test_empty_collection(self):
        c = Collection()
        assert c.count() == 0
        assert c.is_empty()

    def test_count(self):
        c = Collection([1, 2, 3])
        assert c.count() == 3

    def test_all_returns_items(self):
        c = Collection([10, 20])
        assert c.all() == [10, 20]

    def test_iteration(self):
        items = [1, 2, 3]
        c = Collection(items)
        assert list(c) == items

    def test_getitem(self):
        c = Collection(["a", "b", "c"])
        assert c[0] == "a"
        assert c[-1] == "c"


class TestCollectionFirstLast:
    def test_first_without_callback(self):
        assert Collection([5, 6, 7]).first() == 5

    def test_first_with_callback(self):
        c = Collection([1, 2, 3, 4])
        result = c.first(lambda x: x > 2)
        assert result == 3

    def test_last_without_callback(self):
        assert Collection([1, 2, 3]).last() == 3

    def test_last_with_callback(self):
        c = Collection([1, 2, 3, 4])
        result = c.last(lambda x: x < 3)
        assert result == 2

    def test_first_returns_none_for_empty(self):
        assert Collection([]).first() is None


class TestCollectionMap:
    def test_map_transforms_items(self):
        c = Collection([1, 2, 3])
        result = c.map(lambda x: x * 2)
        assert result.all() == [2, 4, 6]

    def test_map_returns_new_collection(self):
        c = Collection([1, 2, 3])
        result = c.map(lambda x: x)
        assert isinstance(result, Collection)


class TestCollectionFilter:
    def test_filter_keeps_matching_items(self):
        c = Collection([1, 2, 3, 4, 5])
        result = c.filter(lambda x: x % 2 == 0)
        assert result.all() == [2, 4]

    def test_filter_raises_on_non_callable(self):
        with pytest.raises(ValueError):
            Collection([1, 2]).filter("not a callable")


class TestCollectionPluck:
    def test_pluck_values_from_dicts(self):
        c = Collection([{"name": "Alice"}, {"name": "Bob"}])
        result = c.pluck("name")
        assert result.all() == ["Alice", "Bob"]

    def test_pluck_with_key(self):
        c = Collection([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}])
        result = c.pluck("name", "id")
        assert result.all() == {1: "Alice", 2: "Bob"}


class TestCollectionChunk:
    def test_chunk_even(self):
        c = Collection([1, 2, 3, 4])
        chunks = c.chunk(2)
        result = [ch.all() for ch in chunks]
        assert result == [[1, 2], [3, 4]]

    def test_chunk_uneven(self):
        c = Collection([1, 2, 3, 4, 5])
        chunks = c.chunk(2)
        result = [ch.all() for ch in chunks]
        assert result == [[1, 2], [3, 4], [5]]

    def test_chunk_size_larger_than_collection(self):
        c = Collection([1, 2])
        chunks = c.chunk(10)
        result = [ch.all() for ch in chunks]
        assert result == [[1, 2]]


class TestCollectionGroupBy:
    def test_group_by_key(self):
        c = Collection(
            [
                {"category": "A", "val": 1},
                {"category": "B", "val": 2},
                {"category": "A", "val": 3},
            ]
        )
        result = c.group_by("category")
        grouped = result.all()
        assert "A" in grouped
        assert "B" in grouped
        assert len(grouped["A"]) == 2
        assert len(grouped["B"]) == 1


class TestCollectionSum:
    def test_sum_numbers(self):
        assert Collection([1, 2, 3]).sum() == 6

    def test_sum_key(self):
        c = Collection([{"price": 10}, {"price": 20}])
        assert c.sum("price") == 30

    def test_sum_empty(self):
        assert Collection([]).sum() == 0


class TestCollectionImplode:
    def test_implode_strings(self):
        result = Collection(["a", "b", "c"]).implode(", ")
        assert result == "a, b, c"

    def test_implode_numbers(self):
        result = Collection([1, 2, 3]).implode("-")
        assert result == "1-2-3"


class TestCollectionMerge:
    def test_merge_adds_items(self):
        c = Collection([1, 2])
        c.merge([3, 4])
        assert c.all() == [1, 2, 3, 4]

    def test_merge_raises_on_non_list(self):
        with pytest.raises(ValueError):
            Collection([1]).merge("not a list")


class TestCollectionUnique:
    def test_unique_primitives(self):
        result = Collection([1, 2, 2, 3, 3]).unique()
        assert len(result.all()) == 3

    def test_unique_by_key(self):
        c = Collection([{"id": 1, "x": "a"}, {"id": 1, "x": "b"}, {"id": 2, "x": "c"}])
        result = c.unique("id")
        assert result.count() == 2


class TestCollectionWhere:
    def test_where_equals(self):
        c = Collection([{"age": 10}, {"age": 20}, {"age": 10}])
        result = c.where("age", 10)
        assert result.count() == 2

    def test_where_greater_than(self):
        c = Collection([{"n": 1}, {"n": 5}, {"n": 10}])
        result = c.where("n", ">", 4)
        assert result.count() == 2


class TestCollectionContains:
    def test_contains_primitive(self):
        c = Collection([1, 2, 3])
        assert c.contains(2) is True
        assert c.contains(99) is False

    def test_contains_with_callback(self):
        c = Collection([1, 2, 3])
        assert c.contains(lambda x: x > 2) is True
        assert c.contains(lambda x: x > 10) is False


class TestCollect:
    def test_collect_returns_collection(self):
        result = collect([1, 2, 3])
        assert isinstance(result, Collection)
        assert result.all() == [1, 2, 3]


class TestFlatten:
    def test_flatten_nested_lists(self):
        result = flatten([[1, 2], [3, [4, 5]]])
        assert result == [1, 2, 3, 4, 5]

    def test_flatten_already_flat(self):
        result = flatten([1, 2, 3])
        assert result == [1, 2, 3]

    def test_flatten_empty(self):
        assert flatten([]) == []

    def test_flatten_deeply_nested(self):
        result = flatten([[[1]], [2, [3]]])
        assert result == [1, 2, 3]


class TestCollectionHTTPUtils:
    def test_http_status_200_ok(self):
        from fastapi_startkit.utils.http import HTTP_STATUS_CODES

        assert HTTP_STATUS_CODES[200] == "200 OK"

    def test_http_status_404_not_found(self):
        from fastapi_startkit.utils.http import HTTP_STATUS_CODES

        assert "404" in HTTP_STATUS_CODES[404]

    def test_http_status_500_internal_server_error(self):
        from fastapi_startkit.utils.http import HTTP_STATUS_CODES

        assert "500" in HTTP_STATUS_CODES[500]

    def test_generate_wsgi_defaults(self):
        from fastapi_startkit.utils.http import generate_wsgi

        env = generate_wsgi()
        assert env["REQUEST_METHOD"] == "GET"
        assert env["PATH_INFO"] == "/"
        assert env["SERVER_PORT"] == "8000"

    def test_generate_wsgi_custom_path_and_method(self):
        from fastapi_startkit.utils.http import generate_wsgi

        env = generate_wsgi(path="/users", method="POST")
        assert env["PATH_INFO"] == "/users"
        assert env["REQUEST_METHOD"] == "POST"

    def test_generate_wsgi_custom_query_string(self):
        from fastapi_startkit.utils.http import generate_wsgi

        env = generate_wsgi(query_string="page=1&limit=10")
        assert env["QUERY_STRING"] == "page=1&limit=10"
