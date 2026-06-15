"""Unit tests for the TestResponse httpx wrapper + fluent assert_json."""

import json as jsonlib

import httpx
import pytest

from fastapi_startkit.fastapi.testing.test_response import TestResponse


def make_response(status_code=200, payload=None):
    content = jsonlib.dumps(payload if payload is not None else {})
    raw = httpx.Response(
        status_code=status_code,
        content=content.encode(),
        headers={"content-type": "application/json"},
    )
    return TestResponse(raw)


def test_passthrough_attributes():
    resp = make_response(200, {"message": "ok"})
    assert resp.status_code == 200
    assert resp.json() == {"message": "ok"}
    assert resp.text == '{"message": "ok"}'


def test_assert_status_and_ok():
    resp = make_response(200, {"a": 1})
    assert resp.assert_status(200).assert_ok() is resp


def test_assert_status_failure_includes_body():
    resp = make_response(500, {"error": "boom"})
    with pytest.raises(AssertionError) as exc:
        resp.assert_status(200)
    assert "boom" in str(exc.value)


def test_assert_created_and_no_content():
    make_response(201, {}).assert_created()
    make_response(204, {}).assert_no_content()


def test_assert_json_fluent_chain():
    resp = make_response(200, {"id": 1, "name": "Bedu"})
    resp.assert_ok().assert_json(lambda j: j.where("id", 1).where("name", "Bedu").etc())


def test_assert_json_strict_failure_on_extra_key():
    resp = make_response(200, {"id": 1, "secret": "leak"})
    with pytest.raises(AssertionError) as exc:
        resp.assert_json(lambda j: j.where("id", 1))
    assert "secret" in str(exc.value)


def test_assert_json_exact():
    resp = make_response(200, {"id": 1})
    resp.assert_json(exact={"id": 1})
    with pytest.raises(AssertionError):
        resp.assert_json(exact={"id": 2})


def test_assert_json_structure_wildcard():
    payload = {"teams": [{"name": "Suns", "sport": "b"}, {"name": "Cardinals", "sport": "f"}]}
    resp = make_response(200, payload)
    resp.assert_ok().assert_json_structure({"teams": {"*": ["name", "sport"]}})


def test_assert_json_structure_failure():
    resp = make_response(200, {"teams": [{"name": "Suns"}]})
    with pytest.raises(AssertionError):
        resp.assert_json_structure({"teams": {"*": ["name", "sport"]}})


def test_assert_json_dotted_list_index_scope():
    payload = {"teams": [{"name": "Phoenix Suns", "sport": "basketball"}]}
    resp = make_response(200, payload)
    resp.assert_json(lambda j: j.has("teams", 1).has("teams.0", lambda team: team.where("name", "Phoenix Suns").etc()))
