"""Tests for utils/timezones.py — converting local wall-clock times to UT."""

from datetime import datetime, timezone

import pytest

from w8s_astro_mcp.utils.timezones import (
    TimezoneError,
    local_to_utc,
    utc_engine_args,
    utc_offset_label,
    utc_to_local,
)


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc)


class TestLocalToUtc:
    def test_central_daylight_time_1981(self):
        # US DST was in effect on 1981-05-06, so Chicago was UTC-5 (not -6).
        assert local_to_utc("1981-05-06", "00:50", "America/Chicago") == utc(1981, 5, 6, 5, 50)

    def test_pacific_daylight_time(self):
        assert local_to_utc("1983-08-27", "09:52", "America/Los_Angeles") == utc(1983, 8, 27, 16, 52)

    def test_eastern_standard_time(self):
        assert local_to_utc("2009-12-10", "14:48", "America/New_York") == utc(2009, 12, 10, 19, 48)

    def test_date_rolls_forward_in_utc(self):
        assert local_to_utc("2026-03-18", "22:00", "America/Los_Angeles") == utc(2026, 3, 19, 5, 0)

    def test_date_rolls_backward_in_utc(self):
        assert local_to_utc("2026-01-01", "01:00", "Asia/Tokyo") == utc(2025, 12, 31, 16, 0)

    def test_half_hour_zone(self):
        assert local_to_utc("2026-06-01", "12:00", "Asia/Kolkata") == utc(2026, 6, 1, 6, 30)

    def test_utc_is_unchanged(self):
        assert local_to_utc("2026-06-01", "12:00", "UTC") == utc(2026, 6, 1, 12, 0)

    def test_result_is_timezone_aware_utc(self):
        result = local_to_utc("2026-06-01", "12:00", "America/Chicago")
        assert result.tzinfo is timezone.utc

    def test_seconds_are_accepted_and_ignored(self):
        assert local_to_utc("1981-05-06", "00:50:00", "America/Chicago") == utc(1981, 5, 6, 5, 50)

    def test_dst_spring_forward_gap_shifts_forward(self):
        # 02:30 does not exist on 2026-03-08 in Chicago (02:00 -> 03:00). It is read with the
        # pre-transition offset (UTC-6), i.e. the same instant as 03:30 CDT.
        assert local_to_utc("2026-03-08", "02:30", "America/Chicago") == utc(2026, 3, 8, 8, 30)

    def test_dst_fall_back_ambiguity_takes_first_occurrence(self):
        # 01:30 happens twice on 2026-11-01 in Chicago; the first (CDT, UTC-5) wins.
        assert local_to_utc("2026-11-01", "01:30", "America/Chicago") == utc(2026, 11, 1, 6, 30)


class TestUtcOffsetLabel:
    def test_negative_whole_hours(self):
        assert utc_offset_label("1981-05-06", "00:50", "America/Chicago") == "UTC-5"      # DST in effect

    def test_standard_time(self):
        assert utc_offset_label("2026-01-01", "12:00", "America/Chicago") == "UTC-6"

    def test_half_hour_zone(self):
        assert utc_offset_label("2026-06-01", "12:00", "Asia/Kolkata") == "UTC+5:30"

    def test_utc(self):
        assert utc_offset_label("2026-06-01", "12:00", "UTC") == "UTC+0"

    def test_bad_timezone_raises(self):
        with pytest.raises(TimezoneError):
            utc_offset_label("2026-06-01", "12:00", "Mars/Olympus")


class TestErrors:
    def test_unknown_timezone_names_the_timezone(self):
        with pytest.raises(TimezoneError, match="Mars/Olympus"):
            local_to_utc("2026-06-01", "12:00", "Mars/Olympus")

    def test_empty_timezone(self):
        with pytest.raises(TimezoneError, match="timezone"):
            local_to_utc("2026-06-01", "12:00", "")

    def test_bad_date(self):
        with pytest.raises(TimezoneError, match="date"):
            local_to_utc("06/01/2026", "12:00", "UTC")

    @pytest.mark.parametrize("bad", ["25:00", "12:60", "noon", "", "12"])
    def test_bad_time(self, bad):
        with pytest.raises(TimezoneError, match="time"):
            local_to_utc("2026-06-01", bad, "UTC")

    def test_timezone_error_is_a_value_error(self):
        assert issubclass(TimezoneError, ValueError)


class TestEngineArgs:
    def test_returns_strings_the_engine_expects(self):
        assert utc_engine_args("1981-05-06", "00:50", "America/Chicago") == ("1981-05-06", "05:50")

    def test_date_can_change(self):
        assert utc_engine_args("2026-03-18", "22:00", "America/Los_Angeles") == ("2026-03-19", "05:00")

    def test_time_is_zero_padded(self):
        assert utc_engine_args("2026-06-01", "12:00", "Asia/Kolkata") == ("2026-06-01", "06:30")
        assert utc_engine_args("2026-01-01", "12:00", "Asia/Tokyo") == ("2026-01-01", "03:00")


class TestUtcToLocal:
    def test_round_trip(self):
        original = local_to_utc("1981-05-06", "00:50", "America/Chicago")
        back = utc_to_local(original, "America/Chicago")
        assert (back.year, back.month, back.day, back.hour, back.minute) == (1981, 5, 6, 0, 50)

    def test_uses_dst_rules_of_that_instant(self):
        # The same UT clock time is a different local time either side of the 2026 US DST change.
        before = utc_to_local(utc(2026, 3, 8, 6, 0), "America/Chicago")    # CST, UTC-6
        after = utc_to_local(utc(2026, 3, 8, 12, 0), "America/Chicago")    # CDT, UTC-5
        assert (before.hour, after.hour) == (0, 7)

    def test_naive_input_is_rejected(self):
        with pytest.raises(TimezoneError):
            utc_to_local(datetime(2026, 3, 8, 6, 0), "America/Chicago")
