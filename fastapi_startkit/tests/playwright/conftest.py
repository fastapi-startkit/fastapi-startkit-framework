from pathlib import Path

import pytest
import pytest_asyncio

pytest.importorskip("playwright")

from fastapi_startkit.playwright import browser_session


async def installed(name: str) -> bool:
    return Path(getattr(await browser_session.driver(), name).executable_path).exists()


@pytest_asyncio.fixture(loop_scope="session")
async def requires_chromium():
    if not await installed("chromium"):
        pytest.skip("Chromium is not installed; run `playwright install chromium`.")
