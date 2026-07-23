"""Tests for the Resource base class."""

from fastapi_startkit.mcp.resource import Resource


# ---------------------------------------------------------------------------
# Concrete resource implementations
# ---------------------------------------------------------------------------


class StatusResource(Resource):
    uri = "resource:///status"
    name = "status"
    description = "Application status."
    mime_type = "text/plain"

    async def read(self, **kwargs) -> str:
        return "ok"


class JsonResource(Resource):
    uri = "resource:///data.json"
    name = "data"
    mime_type = "application/json"

    async def read(self, **kwargs) -> str:
        return '{"key": "value"}'


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResourceToJson:
    def test_uri_serialised(self):
        assert StatusResource().to_json()["uri"] == "resource:///status"

    def test_name_serialised(self):
        assert StatusResource().to_json()["name"] == "status"

    def test_mime_type_serialised(self):
        assert StatusResource().to_json()["mimeType"] == "text/plain"

    def test_description_serialised(self):
        assert StatusResource().to_json()["description"] == "Application status."

    def test_description_omitted_when_none(self):
        data = JsonResource().to_json()
        assert "description" not in data

    def test_json_mime_type(self):
        assert JsonResource().to_json()["mimeType"] == "application/json"


class TestResourceRead:
    async def test_read_returns_string(self):
        result = await StatusResource().read()
        assert result == "ok"

    async def test_read_returns_json_string(self):
        result = await JsonResource().read()
        import json

        assert json.loads(result) == {"key": "value"}

    async def test_read_accepts_kwargs(self):
        # Should not raise even when extra kwargs passed
        result = await StatusResource().read(extra="ignored")
        assert isinstance(result, str)


class TestResourceDefaults:
    def test_default_mime_type(self):
        # Verify class-level default
        assert Resource.mime_type == "text/plain"
