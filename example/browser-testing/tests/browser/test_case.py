from fastapi_startkit.playwright import BrowserTestCase


class TestCase(BrowserTestCase):
    def get_application(self):
        from bootstrap.application import app

        return app
