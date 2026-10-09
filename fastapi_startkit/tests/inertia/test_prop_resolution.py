import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from fastapi_startkit.inertia import Inertia, InertiaMiddleware, Prop, ScrollMetadata
from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.inertia import InertiaResponse
from fastapi_startkit.masoniteorm.pagination import LengthAwarePaginator


class Calls:
    def __init__(self):
        self.names: list[str] = []

    def returning(self, name, value):
        def callback():
            self.names.append(name)
            return value

        return callback


@pytest.fixture(autouse=True)
def reset_inertia():
    Inertia._instance = None
    yield
    Inertia._instance = None


@pytest.fixture
def container():
    templates = MagicMock()
    templates.TemplateResponse.side_effect = lambda request, view, context: JSONResponse(context["page"])
    with patch("fastapi_startkit.application.app") as app:
        app.return_value.has.side_effect = lambda key: key == "templates"
        app.return_value.make.return_value = templates
        yield app


def client_for(props_factory, component="Page", raise_server_exceptions=True):
    app = FastAPI()
    app.add_middleware(InertiaMiddleware)

    @app.get("/page")
    async def page():
        return Inertia.render(component, props_factory())

    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def without_errors(page):
    page["props"].pop("errors", None)
    return page


def visit(client, **headers):
    return without_errors(client.get("/page", headers={Header.INERTIA: "true", **headers}).json())


def partial(client, only=None, except_=None, component="Page", **headers):
    extra = {Header.INERTIA_PARTIAL_COMPONENT: component}
    if only is not None:
        extra[Header.INERTIA_PARTIAL_DATA] = only
    if except_ is not None:
        extra[Header.INERTIA_PARTIAL_EXCEPT] = except_
    return visit(client, **extra, **headers)


def html_visit(client):
    return without_errors(client.get("/page").json())


def test_always_props_survive_partial_reloads_that_exclude_them(container):
    calls = Calls()
    client = client_for(
        lambda: {
            "flash": Inertia.always(calls.returning("flash", "saved")),
            "users": ["taylor"],
            "stats": 1,
        }
    )

    page = partial(client, only="users")
    assert page["props"] == {"flash": "saved", "users": ["taylor"]}

    page = partial(client, except_="flash")
    assert page["props"]["flash"] == "saved"
    assert calls.names == ["flash", "flash"]

    assert html_visit(client)["props"]["flash"] == "saved"


def test_deferred_props_are_listed_by_group_and_loaded_by_partial_reload(container):
    calls = Calls()
    client = client_for(
        lambda: {
            "user": "taylor",
            "stats": Inertia.defer(calls.returning("stats", 42)),
            "chart": Inertia.defer(calls.returning("chart", [1, 2]), group="sidebar"),
            "feed": Inertia.lazy(calls.returning("feed", [])).group("sidebar"),
        }
    )

    for page in (visit(client), html_visit(client)):
        assert page["props"] == {"user": "taylor"}
        assert page["deferredProps"] == {"default": ["stats"], "sidebar": ["chart", "feed"]}
    assert calls.names == []

    page = partial(client, only="chart,feed")
    assert page["props"] == {"chart": [1, 2], "feed": []}
    assert "deferredProps" not in page
    assert calls.names == ["chart", "feed"]


def test_merge_props_emit_merge_prepend_and_match_metadata(container):
    client = client_for(
        lambda: {
            "posts": Inertia.merge([1]).match_on("id"),
            "notifications": Inertia.merge([2]).prepend(),
            "feed": Inertia.merge({"data": [3], "meta": {}}).append_at("data").prepend_at("meta.items"),
            "logs": Prop([4]).prepend().append(),
            "deferred": Inertia.defer(lambda: [5]).merge(),
        }
    )

    page = visit(client)
    assert page["mergeProps"] == ["posts", "feed.data", "logs", "deferred"]
    assert page["prependProps"] == ["notifications", "feed.meta.items"]
    assert page["matchPropsOn"] == ["posts.id"]

    page = visit(client, **{Header.INERTIA_RESET: "posts,feed"})
    assert page["mergeProps"] == ["logs", "deferred"]
    assert "matchPropsOn" not in page

    page = partial(client, only="posts")
    assert page["mergeProps"] == ["posts"]
    assert "prependProps" not in page


def test_deep_merge_props_are_listed_with_match_on(container):
    client = client_for(lambda: {"settings": Inertia.deep_merge({"a": {"b": 1}}).match_on("items.id")})

    page = visit(client)
    assert page["deepMergeProps"] == ["settings"]
    assert page["matchPropsOn"] == ["settings.items.id"]
    assert "mergeProps" not in page


def test_once_props_are_remembered_and_skipped_when_the_client_has_them(container):
    calls = Calls()
    client = client_for(
        lambda: {
            "plans": Inertia.once(calls.returning("plans", ["pro"])),
            "countries": Inertia.once(calls.returning("countries", ["np"])).once_as("geo").until(60),
            "rates": Inertia.once(calls.returning("rates", [1])).until(timedelta(minutes=1)).fresh(),
        }
    )

    before = int(time.time())
    page = visit(client)
    assert page["props"] == {"plans": ["pro"], "countries": ["np"], "rates": [1]}
    assert page["onceProps"]["plans"] == {"prop": "plans", "expiresAt": None}
    assert page["onceProps"]["geo"]["prop"] == "countries"
    assert (before + 60) * 1000 <= page["onceProps"]["geo"]["expiresAt"] <= (int(time.time()) + 60) * 1000

    calls.names.clear()
    page = visit(client, **{Header.INERTIA_EXCEPT_ONCE_PROPS: "plans,geo,rates"})
    assert page["props"] == {"rates": [1]}
    assert set(page["onceProps"]) == {"plans", "geo", "rates"}
    assert calls.names == ["rates"]

    page = partial(client, only="plans", **{Header.INERTIA_EXCEPT_ONCE_PROPS: "plans"})
    assert page["props"] == {"plans": ["pro"]}
    assert list(page["onceProps"]) == ["plans"]

    client.headers[Header.INERTIA_EXCEPT_ONCE_PROPS] = "plans"
    assert "plans" in html_visit(client)["props"]


def test_deferred_once_props_are_not_listed_again_once_loaded(container):
    client = client_for(lambda: {"plans": Inertia.defer(lambda: ["pro"]).once()})

    assert visit(client)["deferredProps"] == {"default": ["plans"]}
    page = visit(client, **{Header.INERTIA_EXCEPT_ONCE_PROPS: "plans"})
    assert "deferredProps" not in page
    assert page["onceProps"] == {"plans": {"prop": "plans", "expiresAt": None}}


class Items:
    def __init__(self, items):
        self.items = items

    def __len__(self):
        return len(self.items)

    def serialize(self):
        return self.items


def test_scroll_props_emit_pagination_metadata_and_honour_merge_intent(container):
    client = client_for(
        lambda: {
            "users": Inertia.scroll(LengthAwarePaginator(Items(["a", "b"]), per_page=2, current_page=2, total=6)),
        }
    )

    page = visit(client)
    assert page["props"]["users"]["data"] == ["a", "b"]
    assert page["scrollProps"] == {
        "users": {"pageName": "page", "previousPage": 1, "nextPage": 3, "currentPage": 2, "reset": False}
    }
    assert page["mergeProps"] == ["users.data"]
    assert html_visit(client)["scrollProps"]["users"]["currentPage"] == 2

    page = visit(client, **{Header.INERTIA_INFINITE_SCROLL_MERGE_INTENT: "prepend"})
    assert page["prependProps"] == ["users.data"]
    assert "mergeProps" not in page

    page = visit(client, **{Header.INERTIA_RESET: "users"})
    assert page["scrollProps"]["users"]["reset"] is True
    assert "mergeProps" not in page


def test_scroll_with_resolves_lazily_with_custom_wrapper_and_metadata(container):
    calls = Calls()

    class Page:
        def scroll_metadata(self):
            return ScrollMetadata.cursors("cursor", previous=None, next="abc")

        def serialize(self):
            calls.names.append("page")
            return {"items": [1]}

    client = client_for(
        lambda: {
            "feed": Inertia.scroll_with(Page).wrapper("items"),
            "logs": Inertia.scroll([1, 2], ScrollMetadata.pages("logs", 1, 1)),
            "plain": Prop([1]).wrapper("ignored"),
        }
    )

    page = visit(client)
    assert page["props"]["feed"] == {"items": [1]}
    assert page["props"]["logs"] == [1, 2]
    assert page["scrollProps"] == {
        "feed": {"pageName": "cursor", "previousPage": None, "nextPage": "abc", "currentPage": 1, "reset": False},
        "logs": {"pageName": "logs", "previousPage": None, "nextPage": None, "currentPage": 1, "reset": False},
    }
    assert page["mergeProps"] == ["feed.items", "logs.data"]

    calls.names.clear()
    partial(client, only="logs")
    assert calls.names == []


def test_unrescued_prop_errors_fail_the_response(container):
    def broken():
        raise RuntimeError("boom")

    client = client_for(lambda: {"stats": broken}, raise_server_exceptions=False)

    assert client.get("/page", headers={Header.INERTIA: "true"}).status_code == 500


def test_rescued_props_are_dropped_and_listed(container):
    def broken():
        raise RuntimeError("boom")

    client = client_for(
        lambda: {
            "user": "taylor",
            "stats": Inertia.defer(broken).rescue(),
            "chart": Prop(broken).rescue(),
        }
    )

    page = visit(client)
    assert page["props"] == {"user": "taylor"}
    assert page["rescuedProps"] == ["chart"]
    assert page["deferredProps"] == {"default": ["stats"]}

    page = partial(client, only="stats")
    assert page["props"] == {}
    assert page["rescuedProps"] == ["stats"]
    assert "rescuedProps" not in partial(client, only="user")


def test_nested_props_resolve_recursively_and_partials_match_dot_paths(container):
    calls = Calls()
    client = client_for(
        lambda: {
            "auth": {
                "user": calls.returning("user", "taylor"),
                "permissions": Inertia.defer(calls.returning("permissions", ["admin"])),
                "teams": Inertia.merge(["a"]),
            },
            "auth.locale": "en",
            "stats": calls.returning("stats", 1),
        }
    )

    page = visit(client)
    assert page["props"] == {"auth": {"user": "taylor", "teams": ["a"], "locale": "en"}, "stats": 1}
    assert page["deferredProps"] == {"default": ["auth.permissions"]}
    assert page["mergeProps"] == ["auth.teams"]

    calls.names.clear()
    page = partial(client, only="auth.user")
    assert page["props"] == {"auth": {"user": "taylor"}}
    assert calls.names == ["user"]

    page = partial(client, only="auth.permissions")
    assert page["props"] == {"auth": {"permissions": ["admin"]}}

    page = partial(client, only="auth")
    assert set(page["props"]["auth"]) == {"user", "permissions", "teams", "locale"}
    assert page["mergeProps"] == ["auth.teams"]


def test_always_parent_bypasses_filtering_of_its_children(container):
    client = client_for(lambda: {"auth": Inertia.always({"user": "taylor", "team": "core"}), "other": 1})

    assert partial(client, only="other")["props"] == {"auth": {"user": "taylor", "team": "core"}, "other": 1}


def test_partial_except_excludes_props_and_wins_over_only(container):
    calls = Calls()
    client = client_for(
        lambda: {
            "users": calls.returning("users", []),
            "stats": calls.returning("stats", 1),
            "auth": {"user": "taylor", "token": "secret"},
            "lazy": Inertia.optional(calls.returning("lazy", "x")),
        }
    )

    page = partial(client, except_="stats,auth.token")
    assert page["props"] == {"users": [], "auth": {"user": "taylor"}, "lazy": "x"}
    assert calls.names == ["users", "lazy"]

    calls.names.clear()
    page = partial(client, only="users,stats", except_="stats")
    assert page["props"] == {"users": []}
    assert calls.names == ["users"]


def test_partial_reload_of_another_component_is_a_full_visit(container):
    client = client_for(lambda: {"a": 1, "lazy": Inertia.optional(lambda: 2)})

    assert partial(client, only="lazy", component="Other")["props"] == {"a": 1}


def test_shared_props_metadata_lists_top_level_shared_keys(container):
    def share_and_render():
        Inertia.share({"app": "Startkit", "auth.user": "taylor"})
        return {"page": 1}

    client = client_for(share_and_render)
    assert visit(client)["sharedProps"] == ["errors", "app", "auth"]

    def disabled():
        Inertia.expose_shared_prop_keys(False)
        return share_and_render()

    assert "sharedProps" not in visit(client_for(disabled))


async def test_shared_props_metadata_is_omitted_when_empty():
    request = MagicMock()
    request.headers = {Header.INERTIA: "true"}
    request.url = "http://localhost/"

    response = await InertiaResponse("Page", {}, {"a": 1}).to_response(request)

    assert b"sharedProps" not in response.body


async def test_shared_props_are_not_mutated_by_dot_keys():
    request = MagicMock()
    request.headers = {Header.INERTIA: "true"}
    request.url = "http://localhost/"
    shared = {"auth": {"user": "taylor"}}

    await InertiaResponse("Page", shared, {"auth.locale": "en"}).to_response(request)

    assert shared == {"auth": {"user": "taylor"}}


def test_callable_props_receive_the_request(container):
    client = client_for(lambda: {"path": lambda request: request.url.path, "plain": Prop("value")})

    assert visit(client)["props"] == {"path": "/page", "plain": "value"}


def test_scroll_metadata_pages_bounds():
    assert ScrollMetadata.pages("page", 1, 3).to_dict() == {
        "pageName": "page",
        "previousPage": None,
        "nextPage": 2,
        "currentPage": 1,
    }
    assert ScrollMetadata.pages("page", 3, 3).next_page is None


def test_props_leading_to_a_requested_path_do_not_announce_metadata(container):
    client = client_for(lambda: {"auth": Inertia.merge({"user": "taylor", "teams": []}).once()})

    page = partial(client, only="auth.user")
    assert page["props"] == {"auth": {"user": "taylor"}}
    assert "mergeProps" not in page
    assert "onceProps" not in page


def test_scroll_props_without_metadata_skip_scroll_props(container):
    client = client_for(lambda: {"items": Inertia.scroll([1, 2])})

    page = visit(client)
    assert page["props"]["items"] == [1, 2]
    assert "scrollProps" not in page
    assert page["mergeProps"] == ["items.data"]
