from fastapi_startkit.playwright.assertions import Assertions
from fastapi_startkit.playwright.interactions import Interactions

MOBILE_DEVICE = "iPhone 14"
TABLET_DEVICE = "iPad (gen 7)"


class DeviceSelector:
    def __init__(self, page: "Page"):
        self._page = page

    def mobile(self) -> "Page":
        return self._page.device(MOBILE_DEVICE)

    def tablet(self) -> "Page":
        return self._page.device(TABLET_DEVICE)

    def desktop(self) -> "Page":
        return self._page.device(None)

    def device(self, name: str) -> "Page":
        return self._page.device(name)


class Page(Interactions, Assertions):
    def on(self) -> DeviceSelector:
        return DeviceSelector(self)
