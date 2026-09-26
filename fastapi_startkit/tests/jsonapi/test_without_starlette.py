import importlib.util
from types import ModuleType
from unittest.mock import patch

from starlette.responses import Response

from fastapi_startkit.jsonapi import response


def _load_response_module_without_starlette() -> ModuleType:
    real_find_spec = importlib.util.find_spec

    def find_spec(name, *args, **kwargs):
        return None if name == "starlette" else real_find_spec(name, *args, **kwargs)

    # Load an isolated copy so the real module's classes stay untouched for other tests.
    spec = importlib.util.spec_from_file_location("_jsonapi_response_without_starlette", response.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch("importlib.util.find_spec", side_effect=find_spec):
        spec.loader.exec_module(module)
    return module


def test_resources_fall_back_to_plain_objects_without_starlette():
    module = _load_response_module_without_starlette()

    assert not issubclass(module._FastAPICallable, Response)
    assert not issubclass(module.JsonResource, Response)
    assert not issubclass(module.ResourceCollection, Response)
