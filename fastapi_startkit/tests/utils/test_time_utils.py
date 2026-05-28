"""Tests for time utility functions (task #15)."""

import pendulum

from fastapi_startkit.utils.time import cookie_expire_time, migration_timestamp, parse_human_time


class TestParseHumanTime:
    def test_now_returns_current_time(self):
        result = parse_human_time("now")
        assert result is not None
        diff = abs(pendulum.now("GMT").diff(result).in_seconds())
        assert diff < 5

    def test_expired_returns_past_date(self):
        result = parse_human_time("expired")
        assert result < pendulum.now("GMT")

    def test_1_second(self):
        before = pendulum.now("GMT")
        result = parse_human_time("1 second")
        assert result > before

    def test_5_minutes(self):
        result = parse_human_time("5 minutes")
        diff = result.diff(pendulum.now("GMT")).in_minutes()
        assert abs(diff - 5) <= 1

    def test_2_hours(self):
        result = parse_human_time("2 hours")
        diff = result.diff(pendulum.now("GMT")).in_hours()
        assert abs(diff - 2) <= 1

    def test_1_day(self):
        result = parse_human_time("1 day")
        diff = result.diff(pendulum.now("GMT")).in_days()
        assert abs(diff - 1) <= 1

    def test_1_week(self):
        result = parse_human_time("1 week")
        diff = result.diff(pendulum.now("GMT")).in_weeks()
        assert abs(diff - 1) <= 1

    def test_1_month(self):
        result = parse_human_time("1 month")
        diff = result.diff(pendulum.now("GMT")).in_months()
        assert abs(diff - 1) <= 1

    def test_1_year(self):
        result = parse_human_time("1 year")
        diff = result.diff(pendulum.now("GMT")).in_years()
        assert abs(diff - 1) <= 1

    def test_plural_seconds(self):
        result = parse_human_time("30 seconds")
        assert result is not None

    def test_plural_days(self):
        result = parse_human_time("3 days")
        diff = result.diff(pendulum.now("GMT")).in_days()
        assert abs(diff - 3) <= 1


class TestCookieExpireTime:
    def test_returns_cookie_formatted_string(self):
        result = cookie_expire_time("1 day")
        # Cookie format: "Thu, 21 Oct 2021 07:28:00"
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain a comma (day-of-week, date)
        assert "," in result

    def test_now_returns_string(self):
        result = cookie_expire_time("now")
        assert isinstance(result, str)

    def test_expired_returns_past_string(self):
        result = cookie_expire_time("expired")
        assert isinstance(result, str)


class TestMigrationTimestamp:
    def test_returns_string(self):
        ts = migration_timestamp()
        assert isinstance(ts, str)

    def test_format_matches_pattern(self):
        import re

        ts = migration_timestamp()
        assert re.match(r"\d{4}_\d{2}_\d{2}_\d{6}", ts), f"Unexpected format: {ts}"

    def test_contains_current_year(self):
        ts = migration_timestamp()
        year = str(pendulum.now().year)
        assert ts.startswith(year)
