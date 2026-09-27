"""Lifecycle hook dispatch in fastapi_startkit.testing.TestCase."""

from fastapi_startkit.testing.test_case import TestCase


# Built inside a function so pytest does not collect them as unittest classes.
def _case_classes() -> tuple[type[TestCase], type[TestCase]]:
    class BareCase(TestCase):
        calls: list[str]

        def get_application(self):
            raise NotImplementedError

        def runTest(self):
            pass

    class HookedCase(BareCase):
        def startTestRun(self):
            self.calls.append("start")

        def stopTestRun(self):
            self.calls.append("stop")

        async def asyncStartTestRun(self):
            self.calls.append("async_start")

        async def asyncStopTestRun(self):
            self.calls.append("async_stop")

    return BareCase, HookedCase


async def _run_lifecycle(case_class: type[TestCase]) -> list[str]:
    case = case_class()
    case.calls = []
    case.setUp()
    await case.asyncSetUp()
    await case.asyncTearDown()
    case.tearDown()
    return case.calls


async def test_defined_hooks_are_invoked():
    _, hooked = _case_classes()
    assert await _run_lifecycle(hooked) == ["start", "async_start", "async_stop", "stop"]


async def test_missing_hooks_are_skipped():
    bare, _ = _case_classes()
    assert await _run_lifecycle(bare) == []
