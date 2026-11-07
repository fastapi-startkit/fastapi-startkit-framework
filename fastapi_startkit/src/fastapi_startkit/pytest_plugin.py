from importlib.util import find_spec

if find_spec("playwright") is not None and find_spec("pytest_asyncio") is not None:
    from fastapi_startkit.playwright.plugin import (
        browser_session_lifetime,
        pytest_addoption,
        pytest_collection_modifyitems,
        pytest_configure,
        pytest_runtest_makereport,
    )

    __all__ = [
        "browser_session_lifetime",
        "pytest_addoption",
        "pytest_collection_modifyitems",
        "pytest_configure",
        "pytest_runtest_makereport",
    ]
