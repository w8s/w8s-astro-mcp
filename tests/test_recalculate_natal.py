"""Tests for the recalculation tool (w8s-astro-recalculate / w8s_astro_mcp.recalculate_natal).

Charts stored by versions before 0.14.0 were calculated with the local birth time taken as UT.
The tool recalculates them from the stored local birth data. It is dry-run by default, needs an
explicit selection, backs up the database before writing, and is idempotent.
"""

import sqlite3
from unittest.mock import patch

import pytest

from w8s_astro_mcp.database import initialize_database
from w8s_astro_mcp.recalculate_natal import main
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper
from w8s_astro_mcp.utils.ephemeris import EphemerisEngine

ENGINE = EphemerisEngine()

PERSON_A = dict(  # reference chart: Capricorn rising when converted correctly, Scorpio when taken as UT
    name="Person A", birth_date="1981-05-06", birth_time="00:50", birth_location_name="St. Louis, MO",
    birth_latitude=38.627, birth_longitude=-90.199, birth_timezone="America/Chicago",
)
PERSON_B = dict(
    name="Person B", birth_date="1983-08-27", birth_time="09:52", birth_location_name="Somewhere, CA",
    birth_latitude=34.90, birth_longitude=-117.02, birth_timezone="America/Los_Angeles",
)


@pytest.fixture
def env(tmp_path):
    path = tmp_path / "astro.db"
    initialize_database(path, echo=False)
    db = DatabaseHelper(db_path=str(path))
    return db, path, tmp_path / "backups"


def _add(db, wrongly_stored=True, **person):
    """Create a profile and store the chart the way versions before 0.14.0 did (local time as UT)."""
    profile = db.create_profile_with_location(**person)
    if wrongly_stored:
        chart = ENGINE.get_chart(
            person["birth_latitude"], person["birth_longitude"], person["birth_date"], person["birth_time"], "P")
        db.save_natal_chart(profile, chart, 1)
    return profile


def _asc(db, profile):
    return db.get_natal_chart_data(profile)["points"]["Ascendant"]["sign"]


def _run(path, backups, *flags):
    return main(["--db", str(path), "--backup-dir", str(backups), *flags])


def _backups(backups):
    return sorted(backups.glob("*.db")) if backups.exists() else []


# ---------------------------------------------------------------------------
# Safety rails
# ---------------------------------------------------------------------------

def test_requires_an_explicit_selection(env):
    _, path, backups = env
    with pytest.raises(SystemExit) as exc:
        _run(path, backups)
    assert exc.value.code == 2


def test_dry_run_writes_nothing(env, capsys):
    db, path, backups = env
    a = _add(db, **PERSON_A)
    assert _run(path, backups, "--all") == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "would change" in out and "Person A" in out
    assert _asc(db, a) == "Scorpio"                 # still the old, wrong chart
    assert _backups(backups) == []


def test_report_does_not_echo_birth_dates_or_times(env, capsys):
    """The report is easy to paste into an issue or a chat, so it shows the offset applied, not the raw data."""
    db, path, backups = env
    _add(db, **PERSON_A)
    _add(db, **PERSON_B)
    _run(path, backups, "--all")
    out = capsys.readouterr().out
    for private in ("1981", "1983", "00:50", "09:52"):
        assert private not in out
    assert "America/Chicago (UTC-5)" in out and "America/Los_Angeles (UTC-7)" in out


def test_missing_database_is_an_error_and_is_not_created(tmp_path, capsys):
    missing = tmp_path / "nope.db"
    assert main(["--db", str(missing), "--all"]) == 1
    assert "not found" in capsys.readouterr().out.lower()
    assert not missing.exists()


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------

def test_apply_fixes_the_chart_and_backs_up_first(env, capsys):
    db, path, backups = env
    a = _add(db, **PERSON_A)
    assert _run(path, backups, "--all", "--apply") == 0

    assert _asc(db, a) == "Capricorn"
    stored = db.get_natal_chart_data(a)
    expected = ENGINE.get_chart(38.627, -90.199, "1981-05-06", "05:50", "P")
    assert stored["points"]["Ascendant"]["degree"] == pytest.approx(expected["points"]["Ascendant"]["degree"], abs=0.02)
    assert stored["planets"]["Moon"]["degree"] == pytest.approx(expected["planets"]["Moon"]["degree"], abs=0.02)
    assert db.get_profile_by_id(a.id).birth_time == "00:50"          # profile data stays local

    (backup,) = _backups(backups)
    old = sqlite3.connect(str(backup)).execute(
        "select sign from natal_points where profile_id = ? and point_type = 'Ascendant'", (a.id,)).fetchone()
    assert old == ("Scorpio",)                                        # backup holds the pre-fix chart
    assert "Backup:" in capsys.readouterr().out


def test_apply_is_idempotent(env, capsys):
    db, path, backups = env
    _add(db, **PERSON_A)
    _run(path, backups, "--all", "--apply")
    capsys.readouterr()

    assert _run(path, backups, "--all", "--apply") == 0
    assert "already correct" in capsys.readouterr().out
    assert len(_backups(backups)) == 1                                # nothing to change -> no second backup


def test_profile_id_selects_only_that_profile(env):
    db, path, backups = env
    a, b = _add(db, **PERSON_A), _add(db, **PERSON_B)
    wrong_b = db.get_natal_chart_data(b)["points"]["Ascendant"]["sign"]

    assert _run(path, backups, "--profile-id", str(a.id), "--apply") == 0
    assert _asc(db, a) == "Capricorn"
    assert _asc(db, b) == wrong_b


def test_cached_connection_charts_are_invalidated(env):
    db, path, backups = env
    a, b = _add(db, **PERSON_A), _add(db, **PERSON_B)
    conn = db.create_connection("A and B", [a.id, b.id], type="friend")

    with patch.object(DatabaseHelper, "invalidate_connection_charts", autospec=True) as invalidate:
        _run(path, backups, "--profile-id", str(a.id), "--apply")
    assert [call.args[1] for call in invalidate.call_args_list] == [conn.id]


def test_placeholder_times_are_flagged(env, capsys):
    db, path, backups = env
    _add(db, **{**PERSON_B, "name": "Unknown Time", "birth_time": "12:00"})
    _run(path, backups, "--all")
    assert "placeholder" in capsys.readouterr().out


def test_one_bad_timezone_does_not_stop_the_others(env, capsys):
    db, path, backups = env
    a = _add(db, **PERSON_A)
    _add(db, **{**PERSON_B, "name": "Bad Zone", "birth_timezone": "Mars/Olympus"})

    assert _run(path, backups, "--all", "--apply") == 1               # non-zero: something could not be converted
    out = capsys.readouterr().out
    assert "Mars/Olympus" in out and "Bad Zone" in out
    assert _asc(db, a) == "Capricorn"                                 # the good profile was still fixed


# ---------------------------------------------------------------------------
# Saved event charts are opt-in
# ---------------------------------------------------------------------------

def _save_wrong_event(db):
    wrong = ENGINE.get_chart(32.9483, -96.7299, "2026-09-19", "04:00")   # local 04:00 taken as UT
    db.save_event_chart(
        label="richardson", event_date="2026-09-19", event_time="04:00", latitude=32.9483, longitude=-96.7299,
        timezone="America/Chicago", location_name="Richardson, TX", chart=wrong)
    return db.get_event_chart_by_label("richardson")


def _event_asc(db, event_id):
    return db.get_event_chart_positions(event_id)["points"]["Ascendant"]["absolute_position"]


def test_events_are_untouched_unless_requested(env):
    db, path, backups = env
    _add(db, **PERSON_A)
    event = _save_wrong_event(db)
    before = _event_asc(db, event.id)

    _run(path, backups, "--all", "--apply")
    assert _event_asc(db, event.id) == before


def test_events_flag_recalculates_saved_event_charts(env):
    db, path, backups = env
    _add(db, **PERSON_A)
    event = _save_wrong_event(db)

    assert _run(path, backups, "--all", "--events", "--apply") == 0
    expected = ENGINE.get_chart(32.9483, -96.7299, "2026-09-19", "09:00")   # 04:00 CDT = 09:00 UT
    assert _event_asc(db, event.id) == pytest.approx(expected["points"]["Ascendant"]["absolute_position"], abs=0.02)

    positions = db.get_event_chart_positions(event.id)
    assert (len(positions["planets"]), len(positions["houses"]), len(positions["points"])) == (10, 12, 2)
    assert db.get_event_chart_by_label("richardson").event_time == "04:00"   # the stored event time stays local


# ---------------------------------------------------------------------------
# Console script
# ---------------------------------------------------------------------------

def test_run_is_synchronous():
    """pip-generated wrappers call the entry point directly, so it must not be `async def`."""
    import inspect
    from w8s_astro_mcp.recalculate_natal import run

    assert not inspect.iscoroutinefunction(run)


def test_console_script_and_tzdata_are_declared():
    from pathlib import Path

    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'w8s-astro-recalculate = "w8s_astro_mcp.recalculate_natal:run"' in pyproject
    assert '"tzdata' in pyproject          # zoneinfo needs it on Windows and in minimal containers


# ---------------------------------------------------------------------------
# --event LABEL: recalculate individual saved event charts
# ---------------------------------------------------------------------------

def _save_wrong_labelled_event(db, label, time="04:00"):
    """A saved event stored the pre-0.14.0 way (local time taken as UT)."""
    wrong = ENGINE.get_chart(32.9483, -96.7299, "2026-09-19", time)
    db.save_event_chart(
        label=label, event_date="2026-09-19", event_time=time, latitude=32.9483, longitude=-96.7299,
        timezone="America/Chicago", location_name="Richardson, TX", chart=wrong)
    return db.get_event_chart_by_label(label)


def _corrected_event_asc(local_time):
    utc_hour = int(local_time[:2]) + 5                     # America/Chicago, CDT
    fresh = ENGINE.get_chart(32.9483, -96.7299, "2026-09-19", f"{utc_hour:02d}:{local_time[3:]}")
    return fresh["points"]["Ascendant"]["absolute_position"]


class TestEventLabel:
    def test_recalculates_only_the_named_event(self, env):
        db, path, backups = env
        person = _add(db, **PERSON_A)
        first = _save_wrong_labelled_event(db, "first", "04:00")
        second = _save_wrong_labelled_event(db, "second", "06:00")
        second_before = _event_asc(db, second.id)

        assert _run(path, backups, "--event", "first", "--apply") == 0

        assert _event_asc(db, first.id) == pytest.approx(_corrected_event_asc("04:00"), abs=0.02)
        assert _event_asc(db, second.id) == second_before        # other events untouched
        assert _asc(db, person) == "Scorpio"                      # profiles untouched
        assert len(_backups(backups)) == 1

    def test_needs_neither_all_nor_a_profile_nor_the_events_flag(self, env, capsys):
        db, path, backups = env
        _add(db, **PERSON_A)
        _save_wrong_labelled_event(db, "first")
        _run(path, backups, "--event", "first")
        out = capsys.readouterr().out
        assert "event 'first'" in out and "would change" in out
        assert "Person A" not in out and "No matching profiles" not in out

    def test_dry_run_writes_nothing(self, env, capsys):
        db, path, backups = env
        event = _save_wrong_labelled_event(db, "first")
        before = _event_asc(db, event.id)
        assert _run(path, backups, "--event", "first") == 0
        assert "DRY RUN" in capsys.readouterr().out
        assert _event_asc(db, event.id) == before
        assert _backups(backups) == []

    def test_can_be_repeated(self, env):
        db, path, backups = env
        first = _save_wrong_labelled_event(db, "first", "04:00")
        second = _save_wrong_labelled_event(db, "second", "06:00")
        assert _run(path, backups, "--event", "first", "--event", "second", "--apply") == 0
        assert _event_asc(db, first.id) == pytest.approx(_corrected_event_asc("04:00"), abs=0.02)
        assert _event_asc(db, second.id) == pytest.approx(_corrected_event_asc("06:00"), abs=0.02)

    def test_combines_with_a_profile(self, env):
        db, path, backups = env
        person = _add(db, **PERSON_A)
        first = _save_wrong_labelled_event(db, "first", "04:00")
        second = _save_wrong_labelled_event(db, "second", "06:00")
        second_before = _event_asc(db, second.id)

        assert _run(path, backups, "--profile-id", str(person.id), "--event", "first", "--apply") == 0
        assert _asc(db, person) == "Capricorn"
        assert _event_asc(db, first.id) == pytest.approx(_corrected_event_asc("04:00"), abs=0.02)
        assert _event_asc(db, second.id) == second_before

    def test_an_unknown_label_is_an_error_and_writes_nothing(self, env, capsys):
        db, path, backups = env
        event = _save_wrong_labelled_event(db, "first")
        before = _event_asc(db, event.id)

        assert _run(path, backups, "--event", "nope", "--apply") == 1
        out = capsys.readouterr().out
        assert "nope" in out and "Saved event charts: first" in out
        assert _event_asc(db, event.id) == before
        assert _backups(backups) == []

    def test_an_event_selected_twice_is_processed_once(self, env, capsys):
        db, path, backups = env
        _save_wrong_labelled_event(db, "first")
        _run(path, backups, "--all", "--events", "--event", "first")
        assert capsys.readouterr().out.count("event 'first'") == 1

    def test_running_it_again_changes_nothing(self, env, capsys):
        db, path, backups = env
        _save_wrong_labelled_event(db, "first")
        _run(path, backups, "--event", "first", "--apply")
        capsys.readouterr()
        assert _run(path, backups, "--event", "first", "--apply") == 0
        assert "already correct" in capsys.readouterr().out
        assert len(_backups(backups)) == 1

    def test_the_selection_error_mentions_the_new_option(self, env, capsys):
        _, path, backups = env
        with pytest.raises(SystemExit) as exc:
            _run(path, backups)
        assert exc.value.code == 2
        assert "--event LABEL" in capsys.readouterr().err          # "--events" alone would not satisfy this
