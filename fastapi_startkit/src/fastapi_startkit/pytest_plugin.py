from importlib.util import find_spec

import pytest

BROWSER_TESTING = find_spec("playwright") is not None and find_spec("pytest_asyncio") is not None


def pytest_addoption(parser: pytest.Parser) -> None:
    if not BROWSER_TESTING:
        return

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
        "--inspect",
        action="store_true",
        default=False,
        help="Show the browser and pause failed browser tests in the Playwright inspector.",
    )


def pytest_configure(config: pytest.Config) -> None:
    if BROWSER_TESTING:
        from fastapi_startkit.playwright import plugin

        config.pluginmanager.register(plugin, "fastapi_startkit.playwright.plugin")
