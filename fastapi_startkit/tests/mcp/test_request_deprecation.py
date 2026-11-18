import pytest

import fastapi_startkit.mcp as mcp
import fastapi_startkit.mcp.request as mcp_request
from fastapi_startkit.mcp import MCPRequest


@pytest.mark.parametrize("module", [mcp, mcp_request])
def test_json_rpc_request_warns_and_returns_mcp_request(module):
    with pytest.warns(DeprecationWarning, match="use MCPRequest instead"):
        assert module.JsonRpcRequest is MCPRequest


@pytest.mark.parametrize("module", [mcp, mcp_request])
def test_unknown_attributes_still_raise(module):
    with pytest.raises(AttributeError):
        _ = module.NoSuchName
