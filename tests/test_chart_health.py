"""Data-health notice: tell the AI (and through it the user) when stored charts predate the
local-time -> UT fix.

The check recomputes each stored natal chart from the profile's local birth data and compares it
with what is stored. It is condition-based (no "last seen version" state): it repeats, at a polite
rate, until the charts are recalculated, then goes quiet by itself.
"""

import json
from unittest.mock import patch

import pytest

from w8s_astro_mcp.database import initialize_database
from w8s_astro_mcp.recalculate_natal import main as recalculate
from w8s_astro_mcp.utils import chart_health
from w8s_astro_mcp.utils.chart_health import (
    ChartHealth,
    DataNoticeGate,
    check_natal_chart_health,
    data_notice,
)
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper
from w8s_astro_mcp.utils.ephemeris import EphemerisEngine

ENGINE = EphemerisEngine()

PERSON_A = dict(
    name="Person A", birth_date="1981-05-06", birth_time="00:50", birth_location_name="St. Louis, MO",
    birth_latitude=38.627, birth_longitude=-90.199, birth_timezone="America/Chicago",
)
PERSON_B = dict(
    name="Person B", birth_date="1983-08-27", birth_time="09:52", birth_location_name="Somewhere, CA",
    birth_latitude=34.90, birth_longitude=-117.02, birth_timezone="America/Los_Angeles",
)


@pytest.fixture
def env(tmp_path):
    import w8s_astro_mcp.server as srv

    path = tmp_path / "astro.db"
    initialize_database(path, echo=False)
    db = DatabaseHelper(db_path=str(path))
    previous = srv.db_helper
    srv.db_helper = db
    chart_health.reset_cache()
    yield srv, db, path
    srv.db_helper = previous
    chart_health.reset_cache()


def _add_stale(db, **person):
    """A profile whose chart was stored the pre-fix way (local time taken as UT)."""
    profile = db.create_profile_with_location(**person)
    chart = ENGINE.get_chart(
        person["birth_latitude"], person["birth_longitude"], person["birth_date"], person["birth_time"], "P")
    db.save_natal_chart(profile, chart, 1)
    return profile


def _add_correct(srv, db, **person):
    profile = db.create_profile_with_location(**person)
    srv.get_natal_chart_data(profile_id=profile.id)          # calculates the chart correctly
    return profile


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

def test_stale_charts_are_counted(env):
    _, db, _ = env
    _add_stale(db, **PERSON_A)
    _add_stale(db, **PERSON_B)
    assert check_natal_chart_health(db, ENGINE) == ChartHealth(checked=2, stale=2)


def test_correct_charts_are_not_stale(env):
    srv, db, _ = env
    _add_correct(srv, db, **PERSON_A)
    assert check_natal_chart_health(db, ENGINE) == ChartHealth(checked=1, stale=0)


def test_mixed(env):
    srv, db, _ = env
    _add_stale(db, **PERSON_A)
    _add_correct(srv, db, **PERSON_B)
    assert check_natal_chart_health(db, ENGINE) == ChartHealth(checked=2, stale=1)


def test_profiles_without_a_stored_chart_are_not_counted(env):
    _, db, _ = env
    db.create_profile_with_location(**PERSON_A)          # chart is calculated (correctly) on first use
    assert check_natal_chart_health(db, ENGINE) == ChartHealth(checked=0, stale=0)


def test_a_profile_that_cannot_be_checked_is_skipped(env):
    _, db, _ = env
    _add_stale(db, **{**PERSON_B, "birth_timezone": "Mars/Olympus"})
    assert check_natal_chart_health(db, ENGINE) == ChartHealth(checked=0, stale=0)


def test_goes_quiet_after_recalculation(env, tmp_path):
    _, db, path = env
    _add_stale(db, **PERSON_A)
    assert check_natal_chart_health(db, ENGINE).stale == 1
    assert recalculate(["--db", str(path), "--backup-dir", str(tmp_path / "b"), "--all", "--apply"]) == 0
    assert check_natal_chart_health(db, ENGINE) == ChartHealth(checked=1, stale=0)


# ---------------------------------------------------------------------------
# The notice text
# ---------------------------------------------------------------------------

def test_no_notice_when_nothing_is_stale():
    assert data_notice(ChartHealth(checked=3, stale=0)) is None
    assert data_notice(ChartHealth(checked=0, stale=0)) is None


def test_notice_is_factual_and_actionable():
    text = data_notice(ChartHealth(checked=5, stale=2))
    assert text.startswith("Data notice:")
    assert "2 of 5 stored natal charts" in text
    assert "UT" in text and "local" in text
    assert "w8s-astro-recalculate --all" in text and "--apply" in text and "--events" in text
    assert "backs up" in text.lower()
    assert "consent" in text.lower()                 # the AI is asked to tell the user, not to act


def test_notice_singular():
    assert "1 of 1 stored natal chart was" in data_notice(ChartHealth(checked=1, stale=1))


def test_notice_names_no_one():
    assert "Person" not in data_notice(ChartHealth(checked=5, stale=2))


# ---------------------------------------------------------------------------
# Rate limiting and caching
# ---------------------------------------------------------------------------

def test_gate_shows_once_per_interval():
    now = [1000.0]
    gate = DataNoticeGate(interval_seconds=100, clock=lambda: now[0])
    assert gate.should_show() is True
    assert gate.should_show() is False
    now[0] += 99
    assert gate.should_show() is False
    now[0] += 1
    assert gate.should_show() is True


def test_health_is_cached_within_the_ttl(env):
    _, db, _ = env
    _add_stale(db, **PERSON_A)
    now = [0.0]
    with patch.object(chart_health, "check_natal_chart_health", wraps=chart_health.check_natal_chart_health) as check:
        chart_health.current_health(db, ENGINE, ttl_seconds=600, clock=lambda: now[0])
        chart_health.current_health(db, ENGINE, ttl_seconds=600, clock=lambda: now[0])
        assert check.call_count == 1
        now[0] += 601
        chart_health.current_health(db, ENGINE, ttl_seconds=600, clock=lambda: now[0])
        assert check.call_count == 2


# ---------------------------------------------------------------------------
# Through the MCP dispatcher
# ---------------------------------------------------------------------------

@pytest.fixture
def stale_profile(env):
    srv, db, path = env
    profile = _add_stale(db, **PERSON_A)
    db.set_owner_profile(profile.id)                       # compare_charts uses the owner's chart and home
    now = [0.0]
    srv._notice_gate = DataNoticeGate(interval_seconds=1800, clock=lambda: now[0])
    return srv, db, path, profile, now


HOUSES = {"date": "natal"}


@pytest.mark.asyncio
async def test_natal_tool_gets_a_separate_notice_block(stale_profile):
    srv, _, _, profile, _ = stale_profile
    result = await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": profile.id})
    assert len(result) == 2
    assert result[0].text.startswith("# House Placements")           # original output untouched
    assert result[1].text.startswith("Data notice:")
    assert "1 of 1 stored natal chart was" in result[1].text
    assert "Person A" not in result[1].text


@pytest.mark.asyncio
async def test_notice_is_not_repeated_within_the_interval(stale_profile):
    srv, _, _, profile, now = stale_profile
    args = {**HOUSES, "profile_id": profile.id}
    assert len(await srv.call_tool("find_house_placements", args)) == 2
    assert len(await srv.call_tool("find_house_placements", args)) == 1
    now[0] += 1800
    assert len(await srv.call_tool("find_house_placements", args)) == 2


@pytest.mark.asyncio
async def test_tools_that_do_not_use_natal_charts_get_no_notice(stale_profile):
    srv, *_ = stale_profile
    result = await srv.call_tool("list_profiles", {})
    assert len(result) == 1


@pytest.mark.asyncio
async def test_json_output_carries_notices_inside_the_json(stale_profile):
    srv, *_ = stale_profile
    args = {"chart1_date": "natal", "chart2_date": "2026-09-19", "chart2_time": "09:00",
            "orb_multiplier": 0.6, "format": "json"}
    result = await srv.call_tool("compare_charts", args)
    assert len(result) == 1                                          # never a second block for JSON
    payload = json.loads(result[0].text)
    assert len(payload["notices"]) == 1 and payload["notices"][0].startswith("Data notice:")
    result = await srv.call_tool("compare_charts", args)             # JSON is not rate-limited
    assert "notices" in json.loads(result[0].text)


@pytest.mark.asyncio
async def test_nothing_changes_when_charts_are_correct(env):
    srv, db, _ = env
    profile = _add_correct(srv, db, **PERSON_A)
    db.set_owner_profile(profile.id)
    srv._notice_gate = DataNoticeGate()

    text = await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": profile.id})
    assert len(text) == 1

    args = {"chart1_date": "natal", "chart2_date": "2026-09-19", "chart2_time": "09:00",
            "orb_multiplier": 0.6, "format": "json"}
    payload = json.loads((await srv.call_tool("compare_charts", args))[0].text)
    assert "notices" not in payload                                   # additive only when needed


@pytest.mark.asyncio
async def test_a_failing_check_never_breaks_the_tool(stale_profile):
    srv, _, _, profile, _ = stale_profile
    with patch.object(chart_health, "check_natal_chart_health", side_effect=RuntimeError("boom")):
        result = await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": profile.id})
    assert len(result) == 1 and result[0].text.startswith("# House Placements")
