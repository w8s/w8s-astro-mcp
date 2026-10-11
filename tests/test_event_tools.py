"""The event chart and electional tools, called the way an AI client calls them: through `call_tool`.

Nothing of ours is mocked. Expected values come from outside the code: the UT offset of New York in
January is five hours, the Sun stood near 10.6 degrees of Capricorn on 1 January 2000, Mercury was
retrograde from late February to 20 March 2026, and the Moon was waxing until the full moon of
3 March 2026. Known bugs are strict xfail tests that describe the correct behaviour.
"""

import re

import pytest

from tool_harness import add_owner

NEW_YORK = {
    "latitude": 40.7128,
    "longitude": -74.006,
    "timezone": "America/New_York",
    "location_name": "New York, NY",
}
Y2K = {"date": "2000-01-01", "time": "12:00", **NEW_YORK}
WINDOW = {"start_date": "2026-03-01", "end_date": "2026-03-03", **NEW_YORK}


def degrees_of(reply: str, body: str) -> float:
    """The decimal degrees given for a planet or angle in a chart reply, e.g. '- **Sun**: 10.58° ...'."""
    match = re.search(rf"\*\*{body}\*\*: (\d+\.\d+)°", reply)
    assert match, f"no {body} in: {reply}"
    return float(match.group(1))


# -- cast_event_chart --------------------------------------------------------------------------

async def test_cast_converts_local_time_to_ut_and_places_the_planets(tool):
    reply = await tool("cast_event_chart", Y2K)

    assert reply.startswith("# Event Chart: Ad-hoc\n**Date:** 2000-01-01 at 12:00\n")
    assert "**Location:** New York, NY (40.713, -74.006)" in reply
    assert "**UT:** 2000-01-01 17:00" in reply                      # EST is UT-5
    assert 10.4 <= degrees_of(reply, "Sun") <= 10.8                 # the Sun, near 10.6 degrees
    assert re.search(r"\*\*Sun\*\*: [\d.]+° Capricorn", reply)
    assert re.search(r"\*\*Saturn\*\*: [\d.]+° Taurus ℞", reply)    # Saturn was retrograde
    for section in ("## Angles", "## Planets", "## House Cusps"):
        assert section in reply
    assert len(re.findall(r"- \*\*House \d+\*\*", reply)) == 12


async def test_cast_without_a_label_is_not_saved(tool):
    reply = await tool("cast_event_chart", Y2K)
    assert reply.endswith("_Chart not saved (no label provided)_")
    assert (await tool("list_event_charts")).startswith("No saved event charts found.")


async def test_cast_with_a_label_is_saved_listed_and_deletable(tool):
    reply = await tool("cast_event_chart", {**Y2K, "label": "Y2K", "description": "Millennium"})
    assert reply.endswith('✓ Saved as **"Y2K"** — reference with `compare_charts` using `event:Y2K`')
    assert "**Notes:** Millennium" in reply

    listing = await tool("list_event_charts")
    assert listing == (
        "# Saved Event Charts\n\n"
        "## Y2K\n"
        "- **Date/Time:** 2000-01-01 at 12:00\n"
        "- **Location:** New York, NY (40.713, -74.006)\n"
        "- **Notes:** Millennium\n"
        "- **Reference:** `event:Y2K`\n"
    )

    assert await tool("delete_event_chart", {"label": "Y2K", "confirm": True}) == '✓ Event chart "Y2K" deleted'
    assert (await tool("list_event_charts")).startswith("No saved event charts found.")


async def test_a_saved_event_chart_can_be_compared(tool):
    await tool("cast_event_chart", {**Y2K, "label": "Y2K"})
    reply = await tool("compare_charts", {"chart1_date": "event:Y2K", "chart2_date": "event:Y2K"})
    assert reply.startswith("# Aspect Analysis")


async def test_casting_a_taken_label_still_shows_the_chart_but_does_not_overwrite(tool):
    await tool("cast_event_chart", {**Y2K, "label": "Y2K", "description": "first"})

    reply = await tool("cast_event_chart", {**Y2K, "label": "Y2K", "description": "second"})

    assert reply.startswith("# Event Chart: Y2K")
    assert "Chart calculated but not saved" in reply and "already exists" in reply
    listing = await tool("list_event_charts")
    assert "first" in listing and "second" not in listing


async def test_event_charts_can_belong_to_a_profile_and_be_listed_by_it(tool):
    add_owner(tool)
    await tool("cast_event_chart", {**Y2K, "label": "Mine", "profile_id": 1})
    await tool("cast_event_chart", {**Y2K, "label": "Nobody's"})

    everything = await tool("list_event_charts")
    mine = await tool("list_event_charts", {"profile_id": 1})

    assert "## Mine" in everything and "## Nobody's" in everything
    assert "## Mine" in mine and "## Nobody's" not in mine
    assert "- **Profile ID:** 1" in mine


@pytest.mark.parametrize(
    "arguments, fragments",
    [
        ({"date": "2000-01-01"}, ("latitude and longitude are required",)),
        ({**Y2K, "timezone": "Mars/Base"}, ("Unknown timezone 'Mars/Base'",)),
        ({**Y2K, "date": "2000-13-01"}, ("Invalid date '2000-13-01'",)),
    ],
)
async def test_cast_rejects_bad_input_and_saves_nothing(tool, arguments, fragments):
    reply = await tool("cast_event_chart", {**arguments, "label": "Bad"})
    assert reply.startswith("Error")
    for fragment in fragments:
        assert fragment in reply
    assert (await tool("list_event_charts")).startswith("No saved event charts found.")


# -- delete_event_chart ------------------------------------------------------------------------

async def test_deleting_an_event_chart_needs_confirmation(tool):
    await tool("cast_event_chart", {**Y2K, "label": "Y2K"})
    for arguments in ({"label": "Y2K"}, {"label": "Y2K", "confirm": False}):
        assert (await tool("delete_event_chart", arguments)).startswith("Error: confirm must be true")
    assert "## Y2K" in await tool("list_event_charts")


@pytest.mark.parametrize(
    "arguments, expected",
    [
        ({"confirm": True}, "Error: label is required"),
        ({"label": "Nope", "confirm": True}, 'Event chart "Nope" not found'),
    ],
)
async def test_delete_event_chart_rejects_bad_input(tool, arguments, expected):
    assert await tool("delete_event_chart", arguments) == expected


# -- find_electional_windows -------------------------------------------------------------------

async def test_electional_windows_lists_local_times_where_criteria_hold(tool):
    reply = await tool("find_electional_windows", {**WINDOW, "criteria": ["moon_waxing"], "interval_minutes": 360})

    assert reply.startswith("# Electional Windows: 2026-03-01 – 2026-03-03\n**Location:** New York, NY\n")
    assert "**Timezone:** America/New_York (times below are local)" in reply
    assert "## 1. 2026-03-01 00:00 — 1/1 criteria met\n  ✓ moon_waxing" in reply


async def test_electional_windows_report_which_criterion_failed_and_why(tool):
    reply = await tool(
        "find_electional_windows",
        {**WINDOW, "criteria": ["moon_waxing", "no_retrograde_inner"], "interval_minutes": 360},
    )
    # Mercury stood retrograde from late February to 20 March 2026, so the first of March fails.
    assert "2/2 criteria met" not in reply
    assert "✓ moon_waxing" in reply
    assert "✗ no_retrograde_inner (Retrograde: Mercury)" in reply


async def test_the_waning_moon_after_the_full_moon_has_no_waxing_windows(tool):
    # The full moon fell on 3 March 2026, so 4 to 6 March is waning.
    window = {**WINDOW, "start_date": "2026-03-04", "end_date": "2026-03-06"}
    reply = await tool("find_electional_windows", {**window, "criteria": ["moon_waxing"], "interval_minutes": 360})
    assert reply.startswith("No candidates found in 2026-03-04 – 2026-03-06 at 360-minute intervals.")


@pytest.mark.parametrize(
    "arguments, expected",
    [
        ({}, "Error: start_date and end_date are required"),
        ({**WINDOW}, "Error: at least one criterion is required"),
        ({**WINDOW, "criteria": ["moon_waxing"], "start_date": "2026-03-05", "end_date": "2026-03-01"}, "Error: end_date must be after start_date"),
        ({**WINDOW, "criteria": ["moon_waxing"], "start_date": "2000-01-01", "end_date": "2030-01-01"}, "Error: window cannot exceed 90 days"),
        ({**WINDOW, "criteria": ["moon_waxing"], "timezone": "Mars/Base"}, "Error: Unknown timezone 'Mars/Base'. Use an IANA name such as 'America/Chicago'."),
    ],
)
async def test_electional_windows_reject_bad_input(tool, arguments, expected):
    assert await tool("find_electional_windows", arguments) == expected


# -- known bugs: strict xfail, written as the behaviour we want ----------------------------------

async def test_an_unknown_electional_criterion_is_reported(tool):
    reply = await tool("find_electional_windows", {**WINDOW, "criteria": ["moon_waxxing"]})
    assert reply.startswith("Error") and "moon_waxxing" in reply


async def test_casting_for_an_unknown_profile_does_not_show_database_internals(tool):
    reply = await tool("cast_event_chart", {**Y2K, "label": "NoProfile", "profile_id": 99})
    assert "[SQL:" not in reply and "IntegrityError" not in reply
