import pytest

pytest.importorskip("playwright")

pytest_plugins = ["pytester"]


def test_mock_debug_calls_do_not_deselect_other_tests(pytester: pytest.Pytester):
    pytester.makepyfile(
        """
        from unittest.mock import MagicMock

        def test_logs():
            MagicMock().debug()

        def test_fails():
            assert False
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1, failed=1)


def test_browser_debug_option_enables_debugging(pytester: pytest.Pytester):
    pytester.makepyfile(
        """
        from fastapi_startkit.playwright import browser_session

        def test_debug_is_on():
            assert browser_session.debug
        """
    )

    result = pytester.runpytest("--browser-debug")

    result.assert_outcomes(passed=1)


def test_pytest_debug_option_leaves_browser_debugging_off(pytester: pytest.Pytester):
    pytester.makepyfile(
        """
        from fastapi_startkit.playwright import browser_session

        def test_debug_is_off():
            assert not browser_session.debug
        """
    )

    result = pytester.runpytest("--debug", str(pytester.path / "debug.log"))

    result.assert_outcomes(passed=1)
