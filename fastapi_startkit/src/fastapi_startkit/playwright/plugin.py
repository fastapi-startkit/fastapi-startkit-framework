import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from fastapi_startkit.playwright.fixtures import browser_session_lifetime
from fastapi_startkit.playwright.session import CALL_REPORT, browser_session
from fastapi_startkit.playwright.test_case import BrowserTestCase

__all__ = ["browser_session_lifetime"]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini("browser_default", "Browser used when a test does not choose one.", default="chromium")
    parser.addini("browser_timeout", "Milliseconds browser actions and assertions wait.", default="5000")
    parser.addini(
        "browser_screenshot_dir",
        "Directory, relative to the rootdir, for screenshots of failed browser tests.",
        default="tests/browser/screenshots",
    )
    try:
        parser.addoption("--headed", action="store_true", default=False, help="Show the browser during browser tests.")
    except ValueError:
        pass
    parser.addoption(
        "--browser-debug",
        action="store_true",
        default=False,
        help="Show the browser and pause failed browser tests in the Playwright inspector.",
    )


def pytest_configure(config: pytest.Config) -> None:
    browser_session.configure(
        browser=config.getini("browser_default"),
        headed=bool(config.getoption("headed", False)),
        debug=bool(config.getoption("browser_debug", False)),
        timeout=int(config.getini("browser_timeout")),
        screenshot_dir=Path(config.rootpath) / config.getini("browser_screenshot_dir"),
    )


def calls_debug(function: object) -> bool:
    if not callable(function):
        return False

    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (OSError, TypeError, SyntaxError):
        return False

    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "debug"
        and not node.args
        and not node.keywords
        for node in ast.walk(tree)
    )


def is_browser_test(item: pytest.Item) -> bool:
    cls = getattr(item, "cls", None)
    return isinstance(cls, type) and issubclass(cls, BrowserTestCase)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    debugged = [item for item in items if is_browser_test(item) and calls_debug(getattr(item, "function", None))]
    if not debugged:
        return

    config.hook.pytest_deselected(items=[item for item in items if item not in debugged])
    items[:] = debugged
    browser_session.configure(headed=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        item.stash[CALL_REPORT] = report
