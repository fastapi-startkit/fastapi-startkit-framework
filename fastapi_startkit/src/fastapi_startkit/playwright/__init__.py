from .page import DeviceSelector, Page
from .server import LiveServer
from .session import BrowserSession, browser_session
from .test_case import BrowserTestCase


def visit(url: str) -> Page:
    return Page(browser_session, url)


__all__ = ["BrowserSession", "BrowserTestCase", "DeviceSelector", "LiveServer", "Page", "browser_session", "visit"]
