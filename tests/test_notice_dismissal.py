"""The user can dismiss the data notice.

Dismissal is stored in the database (one small additive table, created automatically), is tied to the
set of stale profiles the user has seen, and comes back if a *different* chart becomes stale. It does
not fix anything; it only stops the reminder.
"""

import json
import sqlite3

import pytest

from w8s_astro_mcp.database import DatabaseError, get_session, initialize_database
from w8s_astro_mcp.models import DismissedNotice
from w8s_astro_mcp.utils import chart_health
from w8s_astro_mcp.utils.chart_health import (
    NOTICE_KEY,
    ChartHealth,
    DataNoticeGate,
    check_natal_chart_health,
    data_notice,
    notice_dismissed,
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
    srv._notice_gate = DataNoticeGate(interval_seconds=0)          # never rate-limit in these tests
    chart_health.reset_cache()
    yield srv, db, path
    srv.db_helper = previous
    chart_health.reset_cache()


def _add_stale(db, **person):
    profile = db.create_profile_with_location(**person)
    chart = ENGINE.get_chart(
        person["birth_latitude"], person["birth_longitude"], person["birth_date"], person["birth_time"], "P")
    db.save_natal_chart(profile, chart, 1)
    return profile


HOUSES = {"date": "natal"}


# ---------------------------------------------------------------------------
# Storage: one additive table, created automatically
# ---------------------------------------------------------------------------

def test_table_is_created_on_an_existing_database(tmp_path):
    """An upgrade must not need a migration: opening an older database adds the table."""
    path = tmp_path / "old.db"
    initialize_database(path, echo=False)
    con = sqlite3.connect(str(path))
    con.execute("DROP TABLE dismissed_notices")                    # what a pre-upgrade database looks like
    con.commit()
    con.close()

    initialize_database(path, echo=False)                          # the production start-up path
    assert DatabaseHelper(db_path=str(path)).get_dismissed_notice(NOTICE_KEY) is None


def test_dismiss_stores_a_sorted_unique_list_of_profile_ids(env):
    _, db, _ = env
    db.dismiss_notice(NOTICE_KEY, [3, 1, 3])
    assert db.get_dismissed_notice(NOTICE_KEY) == [1, 3]


def test_dismissing_again_replaces_the_record(env):
    _, db, _ = env
    db.dismiss_notice(NOTICE_KEY, [1])
    db.dismiss_notice(NOTICE_KEY, [2, 5])
    assert db.get_dismissed_notice(NOTICE_KEY) == [2, 5]
    with get_session(db.engine) as session:
        assert session.query(DismissedNotice).count() == 1


def test_restore_removes_the_record(env):
    _, db, _ = env
    db.dismiss_notice(NOTICE_KEY, [1])
    assert db.restore_notice(NOTICE_KEY) is True
    assert db.restore_notice(NOTICE_KEY) is False
    assert db.get_dismissed_notice(NOTICE_KEY) is None


def test_notice_key_is_unique(env):
    _, db, _ = env
    with pytest.raises(DatabaseError):                              # get_session wraps the IntegrityError
        with get_session(db.engine) as session:
            session.add(DismissedNotice(notice_key="k", detail="[]"))
            session.add(DismissedNotice(notice_key="k", detail="[]"))
            session.commit()


# ---------------------------------------------------------------------------
# What "dismissed" means
# ---------------------------------------------------------------------------

def test_health_reports_which_profiles_are_stale(env):
    _, db, _ = env
    a = _add_stale(db, **PERSON_A)
    b = _add_stale(db, **PERSON_B)
    assert check_natal_chart_health(db, ENGINE).stale_ids == (a.id, b.id)


def test_not_dismissed_by_default(env):
    _, db, _ = env
    assert notice_dismissed(db, ChartHealth(checked=2, stale=2, stale_ids=(1, 2))) is False


def test_dismissed_while_the_stale_profiles_are_ones_the_user_has_seen(env):
    _, db, _ = env
    db.dismiss_notice(NOTICE_KEY, [1, 2])
    assert notice_dismissed(db, ChartHealth(checked=2, stale=2, stale_ids=(1, 2))) is True
    assert notice_dismissed(db, ChartHealth(checked=2, stale=1, stale_ids=(2,))) is True     # one was fixed


def test_a_different_stale_profile_brings_the_notice_back(env):
    _, db, _ = env
    db.dismiss_notice(NOTICE_KEY, [1])
    assert notice_dismissed(db, ChartHealth(checked=3, stale=2, stale_ids=(1, 3))) is False


# ---------------------------------------------------------------------------
# The dismiss_data_notice tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_is_listed_and_says_it_is_for_when_the_user_asks(env):
    srv, *_ = env
    tools = {t.name: t for t in await srv.list_tools()}
    tool = tools["dismiss_data_notice"]
    assert tool.inputSchema["properties"]["undo"]["type"] == "boolean"
    assert "only" in tool.description.lower() and "user" in tool.description.lower()


@pytest.mark.asyncio
async def test_dismiss_records_the_current_stale_profiles(env):
    srv, db, _ = env
    a = _add_stale(db, **PERSON_A)
    result = await srv.call_tool("dismiss_data_notice", {})
    text = result[0].text
    assert text.startswith("Dismissed the data notice for 1 stored natal chart")
    assert "w8s-astro-recalculate" in text and "undo" in text        # says how to fix and how to undo
    assert db.get_dismissed_notice(NOTICE_KEY) == [a.id]


@pytest.mark.asyncio
async def test_dismiss_with_nothing_stale_says_so_and_records_nothing(env):
    srv, db, _ = env
    result = await srv.call_tool("dismiss_data_notice", {})
    assert "Nothing to dismiss" in result[0].text
    assert db.get_dismissed_notice(NOTICE_KEY) is None


@pytest.mark.asyncio
async def test_undo_brings_the_notice_back(env):
    srv, db, _ = env
    _add_stale(db, **PERSON_A)
    await srv.call_tool("dismiss_data_notice", {})
    result = await srv.call_tool("dismiss_data_notice", {"undo": True})
    assert "back on" in result[0].text
    assert db.get_dismissed_notice(NOTICE_KEY) is None
    again = await srv.call_tool("dismiss_data_notice", {"undo": True})
    assert "nothing to bring back" in again[0].text


# ---------------------------------------------------------------------------
# End to end through the dispatcher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dismissed_notice_is_no_longer_shown(env):
    srv, db, _ = env
    a = _add_stale(db, **PERSON_A)
    assert len(await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": a.id})) == 2

    await srv.call_tool("dismiss_data_notice", {})
    assert len(await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": a.id})) == 1


@pytest.mark.asyncio
async def test_dismissed_notice_is_also_absent_from_json(env):
    srv, db, _ = env
    a = _add_stale(db, **PERSON_A)
    db.set_owner_profile(a.id)
    args = {"chart1_date": "natal", "chart2_date": "2026-09-19", "chart2_time": "09:00",
            "orb_multiplier": 0.6, "format": "json"}
    assert "notices" in json.loads((await srv.call_tool("compare_charts", args))[0].text)

    await srv.call_tool("dismiss_data_notice", {})
    assert "notices" not in json.loads((await srv.call_tool("compare_charts", args))[0].text)


@pytest.mark.asyncio
async def test_a_new_stale_chart_after_dismissal_shows_the_notice_again(env):
    srv, db, _ = env
    a = _add_stale(db, **PERSON_A)
    await srv.call_tool("dismiss_data_notice", {})
    _add_stale(db, **PERSON_B)                                     # a different chart becomes stale
    chart_health.reset_cache()

    result = await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": a.id})
    assert len(result) == 2
    assert "2 of 2 stored natal charts were" in result[1].text


@pytest.mark.asyncio
async def test_undo_restores_the_notice_end_to_end(env):
    srv, db, _ = env
    a = _add_stale(db, **PERSON_A)
    await srv.call_tool("dismiss_data_notice", {})
    await srv.call_tool("dismiss_data_notice", {"undo": True})
    assert len(await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": a.id})) == 2


@pytest.mark.asyncio
async def test_a_failing_dismissal_lookup_never_breaks_the_tool(env):
    srv, db, _ = env
    a = _add_stale(db, **PERSON_A)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(DatabaseHelper, "get_dismissed_notice", lambda self, key: (_ for _ in ()).throw(RuntimeError("boom")))
        result = await srv.call_tool("find_house_placements", {**HOUSES, "profile_id": a.id})
    assert result[0].text.startswith("# House Placements")


# ---------------------------------------------------------------------------
# The AI is told how to dismiss
# ---------------------------------------------------------------------------

def test_notice_mentions_the_dismiss_tool():
    text = data_notice(ChartHealth(checked=2, stale=1, stale_ids=(1,)))
    assert "dismiss_data_notice" in text
    assert "asks" in text                        # only if the user asks not to be reminded


def test_instructions_mention_the_dismiss_tool():
    import w8s_astro_mcp.server as srv
    assert "dismiss_data_notice" in srv.app.create_initialization_options().instructions
    assert len(srv.app.create_initialization_options().instructions) < 1500
