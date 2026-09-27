from abc import ABC
from typing import TYPE_CHECKING

from fastapi_startkit.testing import TestCase as BaseTestCase

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


class TestCase(BaseTestCase, ABC):
    def get_application(self) -> "Application":
        from bootstrap.application import app

        return app
