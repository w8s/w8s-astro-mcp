"""cast_event_chart and find_electional_windows apply their `timezone` argument.

Both used to hand a local time to the ephemeris as if it were UT. They now convert local -> UT
before calculating and keep local times in what they store and display.
"""

from unittest.mock import MagicMock, patch

import pytest

from w8s_astro_mcp.tools.event_management import (
    handle_cast_event_chart,
    handle_find_electional_windows,
)


class FakeEngine:
    """Records the (date, time) pairs the handlers ask the ephemeris for."""

    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def get_chart(self, latitude=None, longitude=None, date_str=None, time_str="12:00", house_system_code="P"):
        FakeEngine.calls.append((date_str, time_str))
        return {
            "planets": {},
            "houses": {},
            "points": {},
            "metadata": {"date": date_str, "time": f"{time_str}:00"},
        }


@pytest.fixture(autouse=True)
def fake_engine():
    FakeEngine.calls = []
    with patch("w8s_astro_mcp.utils.ephemeris.EphemerisEngine", FakeEngine):
        yield FakeEngine


def _cast_args(**overrides):
    args = {
        "date": "2026-09-19", "time": "04:00", "latitude": 32.9483, "longitude": -96.7299,
        "timezone": "America/Chicago", "location_name": "Richardson, TX",
    }
    args.update(overrides)
    return args


# ---------------------------------------------------------------------------
# cast_event_chart
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cast_converts_local_time_to_ut(fake_engine):
    result = await handle_cast_event_chart(MagicMock(), _cast_args())
    assert fake_engine.calls == [("2026-09-19", "09:00")]          # 04:00 CDT = 09:00 UT
    text = result[0].text
    assert "**Date:** 2026-09-19 at 04:00" in text                  # existing lines unchanged
    assert "**Timezone:** America/Chicago" in text
    assert "**UT:** 2026-09-19 09:00" in text                       # one appended line


@pytest.mark.asyncio
async def test_cast_date_rolls_over_in_ut(fake_engine):
    result = await handle_cast_event_chart(
        MagicMock(), _cast_args(date="2026-03-18", time="22:00", timezone="America/Los_Angeles"))
    assert fake_engine.calls == [("2026-03-19", "05:00")]
    assert "**Date:** 2026-03-18 at 22:00" in result[0].text
    assert "**UT:** 2026-03-19 05:00" in result[0].text


@pytest.mark.asyncio
async def test_cast_saves_the_local_date_and_time(fake_engine):
    db = MagicMock()
    await handle_cast_event_chart(
        db, _cast_args(date="2026-03-18", time="22:00", timezone="America/Los_Angeles", label="evening"))
    kwargs = db.save_event_chart.call_args.kwargs
    assert (kwargs["event_date"], kwargs["event_time"], kwargs["timezone"]) == (
        "2026-03-18", "22:00", "America/Los_Angeles")


@pytest.mark.asyncio
async def test_cast_without_timezone_keeps_ut_behaviour(fake_engine):
    args = _cast_args()
    del args["timezone"]
    result = await handle_cast_event_chart(MagicMock(), args)
    assert fake_engine.calls == [("2026-09-19", "04:00")]           # default timezone is UTC
    assert "**UT:** 2026-09-19 04:00" in result[0].text


@pytest.mark.asyncio
async def test_cast_unknown_timezone_is_a_clear_error(fake_engine):
    result = await handle_cast_event_chart(MagicMock(), _cast_args(timezone="Mars/Olympus"))
    assert result[0].text.startswith("Error")
    assert "Mars/Olympus" in result[0].text
    assert fake_engine.calls == []


@pytest.mark.asyncio
async def test_cast_bad_time_is_a_clear_error(fake_engine):
    result = await handle_cast_event_chart(MagicMock(), _cast_args(time="4pm"))
    assert result[0].text.startswith("Error")
    assert fake_engine.calls == []


# ---------------------------------------------------------------------------
# find_electional_windows
# ---------------------------------------------------------------------------

def _window_args(**overrides):
    args = {
        "start_date": "2026-09-19", "end_date": "2026-09-20", "latitude": 32.9483, "longitude": -96.7299,
        "timezone": "America/Chicago", "location_name": "Richardson, TX", "criteria": ["moon_not_void"],
        "interval_minutes": 360, "max_results": 10,
    }
    args.update(overrides)
    return args


@pytest.fixture
def every_moment_qualifies():
    with patch("w8s_astro_mcp.utils.electional.score_chart", return_value=(["moon_not_void"], {})):
        yield


@pytest.mark.asyncio
async def test_electional_steps_in_ut_and_prints_local_times(fake_engine, every_moment_qualifies):
    result = await handle_find_electional_windows(MagicMock(), _window_args())
    # Local midnight 2026-09-19 (CDT) is 05:00 UT; six-hour steps; the window ends at local midnight on 09-20.
    assert fake_engine.calls == [
        ("2026-09-19", "05:00"), ("2026-09-19", "11:00"), ("2026-09-19", "17:00"),
        ("2026-09-19", "23:00"), ("2026-09-20", "05:00"),
    ]
    text = result[0].text
    for local in ("2026-09-19 00:00", "2026-09-19 06:00", "2026-09-19 12:00", "2026-09-19 18:00", "2026-09-20 00:00"):
        assert local in text
    assert "**Timezone:** America/Chicago" in text


@pytest.mark.asyncio
async def test_electional_steps_are_real_elapsed_time_across_a_dst_change(fake_engine, every_moment_qualifies):
    # US DST began 2026-03-08 at 02:00 local: local labels jump an hour, UT steps stay 6 hours apart.
    result = await handle_find_electional_windows(
        MagicMock(), _window_args(start_date="2026-03-08", end_date="2026-03-09"))
    assert fake_engine.calls == [
        ("2026-03-08", "06:00"), ("2026-03-08", "12:00"), ("2026-03-08", "18:00"), ("2026-03-09", "00:00"),
    ]
    text = result[0].text
    for local in ("2026-03-08 00:00", "2026-03-08 07:00", "2026-03-08 13:00", "2026-03-08 19:00"):
        assert local in text


@pytest.mark.asyncio
async def test_electional_without_timezone_keeps_ut_behaviour(fake_engine, every_moment_qualifies):
    args = _window_args(end_date="2026-09-19")
    del args["timezone"]
    await handle_find_electional_windows(MagicMock(), args)
    assert fake_engine.calls == [("2026-09-19", "00:00")]


@pytest.mark.asyncio
async def test_electional_unknown_timezone_is_a_clear_error(fake_engine):
    result = await handle_find_electional_windows(MagicMock(), _window_args(timezone="Mars/Olympus"))
    assert result[0].text.startswith("Error")
    assert "Mars/Olympus" in result[0].text
    assert fake_engine.calls == []
