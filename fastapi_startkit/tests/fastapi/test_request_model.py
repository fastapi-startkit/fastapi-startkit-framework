"""Tests for ``RequestModel`` signature synthesis (task #722).

``RequestModel`` rewrites a subclass's ``__signature__`` so FastAPI binds each
field from form data (or the query string for ``Query`` fields). These tests
assert the generated parameter defaults and the ``validated()`` filter.
"""

import inspect

from fastapi import Query
from fastapi.params import Form
from fastapi.params import Query as QueryParam
from pydantic_core import PydanticUndefined

from fastapi_startkit.fastapi.requests.model import RequestModel


class SampleRequest(RequestModel):
    name: str
    bio: str = "default-bio"
    page: int = Query(default=1)


class TestGeneratedSignature:
    def setup_method(self):
        self.params = inspect.signature(SampleRequest).parameters

    def test_all_fields_become_parameters(self):
        assert list(self.params) == ["name", "bio", "page"]

    def test_required_field_uses_form_ellipsis(self):
        default = self.params["name"].default
        assert isinstance(default, Form)
        assert default.default is PydanticUndefined

    def test_optional_field_uses_form_with_default(self):
        default = self.params["bio"].default
        assert isinstance(default, Form)
        assert default.default == "default-bio"

    def test_query_field_keeps_query_param(self):
        default = self.params["page"].default
        assert isinstance(default, QueryParam)

    def test_annotations_are_preserved(self):
        assert self.params["name"].annotation is str
        assert self.params["page"].annotation is int


class TestValidated:
    def test_drops_falsy_values(self):
        model = SampleRequest(name="alice", bio="", page=0)
        assert model.validated() == {"name": "alice"}

    def test_keeps_truthy_values(self):
        model = SampleRequest(name="alice", bio="hello", page=3)
        assert model.validated() == {"name": "alice", "bio": "hello", "page": 3}
