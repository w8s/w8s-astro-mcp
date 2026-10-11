"""Characterization tests: pin what seven tools say today, through `call_tool`.

These tools had no test that named them. The registry refactor moves their code, and the tool
output is a public surface (see AGENTS.md), so each reply is frozen here as golden text in
tests/golden/. A refactor that changes a byte fails the test and shows the diff.

Regenerate after an intended change:  UPDATE_GOLDEN=1 pytest tests/test_tool_output_characterization.py
then review `git diff tests/golden` and list the change under **Changed** in the CHANGELOG.

Determinism: the built-in Moshier ephemeris (no data files), a fixed birth date, a temporary
database and home directory, and no network (`urlretrieve` is replaced). Environment-specific
values (pysweph version, temporary paths) are masked before comparison.
"""

import os
import re
from pathlib import Path

import pytest

import w8s_astro_mcp.server as srv
from w8s_astro_mcp.tools import transit_tools
from w8s_astro_mcp.database import initialize_database
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper

GOLDEN_DIR = Path(__file__).parent / "golden"


def _masked(text: str, tmp_path: Path) -> str:
    """Replace values that differ between machines and runs."""
    text = text.replace(str(tmp_path), "<TMP>")
    text = re.sub(r"pysweph version: \S+", "pysweph version: <VERSION>", text)
    return text


def assert_golden(name: str, text: str) -> None:
    path = GOLDEN_DIR / f"{name}.txt"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        return
    assert path.exists(), f"missing golden file {path}; run with UPDATE_GOLDEN=1"
    assert text + "\n" == path.read_text(encoding="utf-8"), f"output changed for {name}"


@pytest.fixture
def tool(tmp_path, monkeypatch):
    """Call a tool through `call_tool`; returns its masked text (all content blocks joined)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))              # Path.home() -> temporary home
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)  # force the built-in Moshier ephemeris
    monkeypatch.chdir(tmp_path)

    db_path = tmp_path / "astro.db"
    initialize_database(db_path, echo=False)
    monkeypatch.setattr(srv, "db_helper", DatabaseHelper(db_path=str(db_path)))
    monkeypatch.setattr(srv, "ephemeris", None)

    async def call(name: str, arguments: dict | None = None) -> str:
        blocks = await srv.call_tool(name, arguments or {})
        return _masked("\n---\n".join(b.text for b in blocks), tmp_path)

    call.home = home
    call.db = srv.db_helper
    call.tmp = tmp_path
    return call


def _add_owner(tool, name="Test Owner", date="1981-05-06", time="00:50"):
    profile = tool.db.create_profile_with_location(
        name=name,
        birth_date=date,
        birth_time=time,
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago",
    )
    tool.db.set_owner_profile(profile.id)
    return profile


def _add_second(tool):
    return tool.db.create_profile_with_location(
        name="Second Person",
        birth_date="1990-01-15",
        birth_time="12:00",
        birth_location_name="Seattle, WA",
        birth_latitude=47.6062,
        birth_longitude=-122.3321,
        birth_timezone="America/Los_Angeles",
    )


# -- check_ephemeris ---------------------------------------------------------------------------

async def test_check_ephemeris_builtin_mode(tool):
    assert_golden("check_ephemeris_moshier", await tool("check_ephemeris"))


# -- download_ephemeris_files ------------------------------------------------------------------

@pytest.fixture
def fake_download(monkeypatch):
    """Replace the network download with a small local write; returns the URLs requested."""
    urls = []

    def fake_urlretrieve(url, dest):
        urls.append(url)
        Path(dest).write_bytes(b"x" * 2048)

    monkeypatch.setattr(srv.urllib.request, "urlretrieve", fake_urlretrieve)
    return urls


async def test_download_ephemeris_files_asks_for_confirmation(tool, fake_download):
    assert_golden("download_ephemeris_files_manifest", await tool("download_ephemeris_files"))
    assert fake_download == []                                  # nothing fetched without confirm
    assert not (tool.home / ".w8s-astro-mcp" / "ephe").exists()


async def test_download_ephemeris_files_confirmed_then_repeated(tool, fake_download):
    first = await tool("download_ephemeris_files", {"confirm": True})
    assert_golden("download_ephemeris_files_confirmed", first)
    ephe = tool.home / ".w8s-astro-mcp" / "ephe"
    assert sorted(p.name for p in ephe.iterdir()) == ["seas_18.se1", "semo_18.se1", "sepl_18.se1"]
    assert [u.rsplit("/", 1)[1] for u in fake_download] == ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]

    # The engine switches to the downloaded files at once, with no restart.
    assert_golden("check_ephemeris_after_download", await tool("check_ephemeris"))

    # A second run skips files that are already there.
    fake_download.clear()
    assert_golden("download_ephemeris_files_repeated", await tool("download_ephemeris_files", {"confirm": True}))
    assert fake_download == []


# -- setup_astro_config / view_config ----------------------------------------------------------

async def test_setup_astro_config_is_deprecated(tool):
    assert_golden("setup_astro_config_deprecated", await tool("setup_astro_config"))


async def test_view_config_without_owner(tool):
    assert_golden("view_config_no_owner", await tool("view_config"))


async def test_view_config_with_owner(tool):
    _add_owner(tool)
    assert_golden("view_config_owner", await tool("view_config"))


# -- get_natal_chart ---------------------------------------------------------------------------

async def test_get_natal_chart_without_owner(tool):
    assert_golden("get_natal_chart_no_owner", await tool("get_natal_chart"))


async def test_get_natal_chart_unknown_profile(tool):
    _add_owner(tool)
    assert_golden("get_natal_chart_unknown_profile", await tool("get_natal_chart", {"profile_id": 999}))


async def test_get_natal_chart_for_owner(tool):
    _add_owner(tool)
    assert_golden("get_natal_chart_owner", await tool("get_natal_chart"))


async def test_get_natal_chart_for_named_profile(tool):
    _add_owner(tool)
    other = _add_second(tool)
    assert_golden("get_natal_chart_profile", await tool("get_natal_chart", {"profile_id": other.id}))


# -- list_connections --------------------------------------------------------------------------

async def test_list_connections_empty(tool):
    assert_golden("list_connections_empty", await tool("list_connections"))


async def test_list_connections_with_one(tool):
    owner = _add_owner(tool)
    other = _add_second(tool)
    await tool("create_connection", {"label": "Pair", "profile_ids": [owner.id, other.id]})
    assert_golden("list_connections_one", await tool("list_connections"))


# -- visualize_natal_chart ---------------------------------------------------------------------

async def test_visualize_natal_chart_without_owner(tool):
    assert_golden("visualize_natal_chart_no_owner", await tool("visualize_natal_chart"))


async def test_visualize_natal_chart_saves_png(tool):
    _add_owner(tool)
    out = tool.tmp / "chart.png"
    text = await tool("visualize_natal_chart", {"output_path": str(out), "title": "Golden"})
    assert_golden("visualize_natal_chart_saved", text)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


async def test_visualize_natal_chart_default_path_is_working_directory(tool):
    _add_owner(tool)
    text = await tool("visualize_natal_chart")
    assert (tool.tmp / "natal_chart.png").exists()
    assert_golden("visualize_natal_chart_default_path", text)


# -- the advertised tool list ------------------------------------------------------------------

async def test_advertised_tools_are_unchanged(tool):
    """Tool names, descriptions and parameter schemas are what a client sees, listed sorted by name."""
    import json

    listed = [t.model_dump(mode="json", exclude_none=True) for t in await srv.list_tools()]
    assert [t["name"] for t in listed] == sorted(t["name"] for t in listed), "tools are listed sorted by name"
    assert len({t["name"] for t in listed}) == len(listed), "a tool is listed twice"
    assert_golden("tool_schemas", json.dumps(listed, indent=2, ensure_ascii=False))


# -- transit tools: get_transits, get_transit_history, find_last_transit, get_ingresses --------

async def _log_two_lookups(tool):
    """Two logged lookups at fixed dates, so history and last-transit have rows to report."""
    await tool("get_transits", {"date": "2026-03-20", "time": "12:00"})
    await tool("get_transits", {"date": "2026-06-21", "time": "12:00"})


async def test_get_transits_without_owner(tool):
    assert_golden("get_transits_no_owner", await tool("get_transits", {"date": "2026-03-20"}))


async def test_get_transits_unknown_profile(tool):
    _add_owner(tool)
    assert_golden("get_transits_unknown_profile", await tool("get_transits", {"date": "2026-03-20", "profile_id": 999}))


async def test_get_transits_at_current_home(tool):
    _add_owner(tool)
    assert_golden("get_transits_home", await tool("get_transits", {"date": "2026-03-20", "time": "09:00"}))


async def test_get_transits_at_birth_location_for_other_profile(tool):
    _add_owner(tool)
    other = _add_second(tool)
    text = await tool("get_transits", {"date": "2026-03-20", "location": "birth", "profile_id": other.id})
    assert_golden("get_transits_birth_other_profile", text)


async def test_get_transits_unknown_place_that_cannot_be_geocoded(tool, monkeypatch):
    _add_owner(tool)
    monkeypatch.setattr(transit_tools, "geocode_location", lambda place: None)
    assert_golden("get_transits_unknown_place", await tool("get_transits", {"date": "2026-03-20", "location": "Nowhereville"}))


async def test_get_transits_geocoded_place_is_not_logged(tool, monkeypatch):
    _add_owner(tool)
    monkeypatch.setattr(
        transit_tools, "geocode_location",
        lambda place: {"name": "Bangkok, Thailand", "latitude": 13.7563, "longitude": 100.5018, "timezone": "Asia/Bangkok"},
    )
    text = await tool("get_transits", {"date": "2026-03-20", "location": "Bangkok"})
    assert_golden("get_transits_geocoded", text)
    assert "No transit history" in await tool("get_transit_history")   # nothing was logged


async def test_get_transit_history(tool):
    _add_owner(tool)
    await _log_two_lookups(tool)
    assert_golden("get_transit_history_all", await tool("get_transit_history"))
    assert_golden("get_transit_history_saturn_after_april", await tool("get_transit_history", {"planet": "Saturn", "after": "2026-04-01"}))
    assert_golden("get_transit_history_limit_one", await tool("get_transit_history", {"limit": 1}))


async def test_get_transit_history_empty_and_errors(tool):
    assert_golden("get_transit_history_no_owner", await tool("get_transit_history"))
    _add_owner(tool)
    assert_golden("get_transit_history_none_logged", await tool("get_transit_history", {"planet": "Mars", "sign": "Aries"}))
    assert_golden("get_transit_history_unknown_profile", await tool("get_transit_history", {"profile_id": 999}))


async def test_find_last_transit(tool):
    _add_owner(tool)
    await _log_two_lookups(tool)
    assert_golden("find_last_transit_sun_in_cancer", await tool("find_last_transit", {"planet": "Sun", "sign": "Cancer"}))
    assert_golden("find_last_transit_not_found", await tool("find_last_transit", {"planet": "Sun", "sign": "Capricorn"}))
    assert_golden("find_last_transit_direct_in_house", await tool("find_last_transit", {"planet": "Moon", "retrograde": False, "house": 1}))


async def test_find_last_transit_errors(tool):
    assert_golden("find_last_transit_no_owner", await tool("find_last_transit", {"planet": "Sun", "sign": "Leo"}))
    _add_owner(tool)
    assert_golden("find_last_transit_unknown_profile", await tool("find_last_transit", {"planet": "Sun", "sign": "Leo", "profile_id": 999}))
    assert_golden("find_last_transit_no_planet", await tool("find_last_transit", {"sign": "Leo"}))
    assert_golden("find_last_transit_no_filter", await tool("find_last_transit", {"planet": "Sun"}))


@pytest.fixture
def frozen_today(monkeypatch):
    """Make date.today() return 2026-10-11 for code that imports `date` from datetime at call time."""
    import datetime as dt

    class FrozenDate(dt.date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 11)

    monkeypatch.setattr(dt, "date", FrozenDate)


async def test_get_ingresses_without_owner(tool, frozen_today):
    assert_golden("get_ingresses_no_owner", await tool("get_ingresses"))


async def test_get_ingresses_upcoming(tool, frozen_today):
    _add_owner(tool)
    assert_golden("get_ingresses_30_days", await tool("get_ingresses"))
    assert_golden("get_ingresses_past_14_days", await tool("get_ingresses", {"days": 14, "future": False}))


async def test_get_ingresses_extended_outer_planets_with_offset(tool, frozen_today):
    _add_owner(tool)
    text = await tool("get_ingresses", {"extended": True, "days": 400, "offset": 365})
    assert_golden("get_ingresses_extended_offset", text)
