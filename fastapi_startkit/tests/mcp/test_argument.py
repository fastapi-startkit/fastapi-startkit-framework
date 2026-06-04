"""Tests for the Argument dataclass."""


from fastapi_startkit.mcp.argument import Argument


class TestArgumentToJson:
    def test_name_is_serialised(self):
        arg = Argument(name="user")
        assert arg.to_json()["name"] == "user"

    def test_required_defaults_to_false(self):
        arg = Argument(name="user")
        assert arg.to_json()["required"] is False

    def test_required_true_is_serialised(self):
        arg = Argument(name="user", required=True)
        assert arg.to_json()["required"] is True

    def test_description_omitted_when_none(self):
        arg = Argument(name="user")
        assert "description" not in arg.to_json()

    def test_description_included_when_set(self):
        arg = Argument(name="user", description="The username")
        result = arg.to_json()
        assert result["description"] == "The username"

    def test_full_argument(self):
        arg = Argument(name="query", description="Search query", required=True)
        result = arg.to_json()
        assert result == {"name": "query", "description": "Search query", "required": True}

    def test_empty_description_is_included(self):
        arg = Argument(name="x", description="")
        assert "description" in arg.to_json()
