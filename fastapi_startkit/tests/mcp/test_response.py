"""Tests for the Response class."""

import json
import pytest

from fastapi_startkit.mcp.response import Response


class TestResponseText:
    def test_text_returns_response_instance(self):
        r = Response.text("hello")
        assert isinstance(r, Response)

    def test_text_content_type(self):
        r = Response.text("hello")
        content = r.to_content()
        assert content[0]["type"] == "text"

    def test_text_content_value(self):
        r = Response.text("hello world")
        assert r.to_content()[0]["text"] == "hello world"

    def test_text_empty_string(self):
        r = Response.text("")
        assert r.to_content()[0]["text"] == ""


class TestResponseStructure:
    def test_structure_returns_response_instance(self):
        r = Response.structure({"key": "val"})
        assert isinstance(r, Response)

    def test_structure_content_type(self):
        r = Response.structure({"key": "val"})
        assert r.to_content()[0]["type"] == "resource"

    def test_structure_contains_resource_key(self):
        r = Response.structure({"key": "val"})
        item = r.to_content()[0]
        assert "resource" in item

    def test_structure_mime_type(self):
        r = Response.structure({"key": "val"})
        assert r.to_content()[0]["resource"]["mimeType"] == "application/json"

    def test_structure_serialises_data(self):
        data = {"status": "ok", "count": 42}
        r = Response.structure(data)
        stored_text = r.to_content()[0]["resource"]["text"]
        assert json.loads(stored_text) == data


class TestResponseEmpty:
    def test_empty_returns_response_instance(self):
        r = Response.empty()
        assert isinstance(r, Response)

    def test_empty_content_is_list(self):
        r = Response.empty()
        assert r.to_content() == []


class TestToContent:
    def test_returns_list(self):
        r = Response.text("x")
        assert isinstance(r.to_content(), list)

    def test_single_item_for_text(self):
        r = Response.text("x")
        assert len(r.to_content()) == 1
