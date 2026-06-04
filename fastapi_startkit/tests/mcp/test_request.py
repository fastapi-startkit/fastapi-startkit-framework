"""Tests for the JsonRpcRequest model."""


from fastapi_startkit.mcp.request import JsonRpcRequest


class TestJsonRpcRequestParsing:
    def test_parses_method(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="tools/list", id=1)
        assert req.method == "tools/list"

    def test_parses_id_integer(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="initialize", id=42)
        assert req.id == 42

    def test_parses_id_string(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="initialize", id="abc")
        assert req.id == "abc"

    def test_parses_params(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="tools/call", params={"name": "add"}, id=1)
        assert req.params == {"name": "add"}

    def test_params_defaults_to_none(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="tools/list", id=1)
        assert req.params is None

    def test_default_jsonrpc_version(self):
        req = JsonRpcRequest(method="tools/list")
        assert req.jsonrpc == "2.0"


class TestNotification:
    def test_notification_has_no_id(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="ping")
        assert req.id is None

    def test_is_notification_true_when_no_id(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="ping")
        assert req.is_notification is True

    def test_is_notification_false_when_id_present(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="ping", id=1)
        assert req.is_notification is False

    def test_is_notification_false_for_id_zero(self):
        req = JsonRpcRequest(jsonrpc="2.0", method="ping", id=0)
        assert req.is_notification is False
