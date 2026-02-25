"""Tests for Phase 8 event chart tools and db_helper methods.

Covers:
- save_event_chart / list_event_charts / get_event_chart_positions / delete_event_chart
- handle_cast_event_chart (no save + with save)
- handle_list_event_charts
- handle_delete_event_chart
- score_chart (electional utility)
- find_electional_windows handler (mocked ephemeris)
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import sys
import types

from w8s_astro_mcp.utils.db_helpers import DatabaseHelper
from w8s_astro_mcp.utils.electional import score_chart
from w8s_astro_mcp.tools.event_management import (
    handle_cast_event_chart,
    handle_list_event_charts,
    handle_delete_event_chart,
    handle_find_electional_windows,
    EVENT_TOOL_NAMES,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_db(tmp_path):
    """Fresh SQLite database for each test, with all models registered and
    HouseSystem seed data populated (required for event FK constraints)."""
    # Import all models so Base.metadata is fully populated before table creation
    from w8s_astro_mcp.models import (  # noqa: F401
        HouseSystem, HOUSE_SYSTEM_SEED_DATA, Location, Profile,
        NatalPlanet, NatalHouse, NatalPoint,
        TransitLookup, TransitPlanet, TransitHouse, TransitPoint,
        Connection, ConnectionMember, ConnectionChart,
        ConnectionPlanet, ConnectionHouse, ConnectionPoint,
        Event, EventPlanet, EventHouse, EventPoint,
    )
    from w8s_astro_mcp.database import get_session

    db_path = str(tmp_path / "test_events.db")
    helper = DatabaseHelper(db_path=db_path)

    # Seed house systems (required for house_system_id FK in events table)
    with get_session(helper.engine) as session:
        for data in HOUSE_SYSTEM_SEED_DATA:
            session.add(HouseSystem(**data))
        session.commit()

    return helper


@pytest.fixture
def mock_ephemeris_engine():
    """Inject a fake ephemeris module into sys.modules so handlers that do
    `from ..utils.ephemeris import EphemerisEngine, EphemerisError` don't
    require swisseph to be installed."""
    fake_module = types.ModuleType("w8s_astro_mcp.utils.ephemeris")

    class FakeEphemerisError(Exception):
        pass

    class FakeEngine:
        def get_chart(self, **kwargs):
            return SAMPLE_CHART

    fake_module.EphemerisEngine = FakeEngine
    fake_module.EphemerisError = FakeEphemerisError

    module_key = "w8s_astro_mcp.utils.ephemeris"
    original = sys.modules.get(module_key)
    sys.modules[module_key] = fake_module
    yield FakeEngine
    if original is None:
        sys.modules.pop(module_key, None)
    else:
        sys.modules[module_key] = original


# ============================================================================
# Sample chart data (used across multiple tests)
# ============================================================================

SAMPLE_CHART = {
    "planets": {
        "Sun": {
            "degree": 15.41, "sign": "Taurus",
            "house_number": 7, "is_retrograde": False,
        },
        "Moon": {
            "degree": 11.86, "sign": "Gemini",
            "house_number": 7, "is_retrograde": False,
        },
        "Mercury": {
            "degree": 25.15, "sign": "Taurus",
            "house_number": 7, "is_retrograde": False,
        },
        "Venus": {
            "degree": 22.87, "sign": "Taurus",
            "house_number": 7, "is_retrograde": False,
        },
        "Mars": {
            "degree": 8.01, "sign": "Taurus",
            "house_number": 6, "is_retrograde": False,
        },
        "Jupiter": {
            "degree": 1.15, "sign": "Libra",
            "house_number": 1, "is_retrograde": False,
        },
    },
    "houses": {
        "1": {"degree": 14.96, "sign": "Scorpio"},
        "7": {"degree": 14.96, "sign": "Taurus"},
    },
    "points": {
        "ASC": {"degree": 14.96, "sign": "Scorpio"},
        "MC":  {"degree": 23.71, "sign": "Leo"},
    },
    "metadata": {
        "date": "2026-02-23",
        "time": "12:00:00",
        "latitude": 32.0,
        "longitude": -96.0,
        "house_system": "Placidus",
    },
}


# ============================================================================
# db_helper event methods
# ============================================================================

class TestSaveEventChart:
    def test_save_and_retrieve(self, tmp_db):
        tmp_db.save_event_chart(
            label="test-event",
            event_date="2026-02-23",
            event_time="12:00",
            latitude=32.0,
            longitude=-96.0,
            timezone="America/Chicago",
            location_name="Dallas, TX",
            chart=SAMPLE_CHART,
        )
        events = tmp_db.list_event_charts()
        assert len(events) == 1
        assert events[0].label == "test-event"
        assert events[0].event_date == "2026-02-23"
        assert events[0].location_name == "Dallas, TX"

    def test_duplicate_label_raises(self, tmp_db):
        tmp_db.save_event_chart(
            label="dup", event_date="2026-01-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Null Island", chart=SAMPLE_CHART,
        )
        with pytest.raises(ValueError, match="already exists"):
            tmp_db.save_event_chart(
                label="dup", event_date="2026-01-02", event_time="12:00",
                latitude=0.0, longitude=0.0, timezone="UTC",
                location_name="Null Island", chart=SAMPLE_CHART,
            )

    def test_optional_fields_none(self, tmp_db):
        tmp_db.save_event_chart(
            label="no-extras", event_date="2026-03-01", event_time="09:00",
            latitude=51.5, longitude=-0.1, timezone="Europe/London",
            location_name="London, UK", chart=SAMPLE_CHART,
            description=None, profile_id=None,
        )
        events = tmp_db.list_event_charts()
        assert events[0].description is None
        assert events[0].profile_id is None

    def test_with_description_and_profile(self, tmp_db):
        # Create a real profile so the FK is satisfied
        profile = tmp_db.create_profile_with_location(
            name="Test Person", birth_date="1990-01-01", birth_time="12:00",
            birth_location_name="New York, NY",
            birth_latitude=40.7, birth_longitude=-74.0,
            birth_timezone="America/New_York",
        )
        tmp_db.save_event_chart(
            label="with-extras", event_date="2026-04-01", event_time="18:00",
            latitude=40.7, longitude=-74.0, timezone="America/New_York",
            location_name="New York, NY", chart=SAMPLE_CHART,
            description="Company launch", profile_id=profile.id,
        )
        events = tmp_db.list_event_charts()
        ev = events[0]
        assert ev.description == "Company launch"
        assert ev.profile_id == profile.id


class TestListEventCharts:
    def test_empty(self, tmp_db):
        assert tmp_db.list_event_charts() == []

    def test_ordered_by_date(self, tmp_db):
        for date in ["2026-03-01", "2026-01-15", "2026-06-10"]:
            tmp_db.save_event_chart(
                label=f"ev-{date}", event_date=date, event_time="12:00",
                latitude=0.0, longitude=0.0, timezone="UTC",
                location_name="Test", chart=SAMPLE_CHART,
            )
        events = tmp_db.list_event_charts()
        dates = [e.event_date for e in events]
        assert dates == sorted(dates)

    def test_filter_by_profile_id(self, tmp_db):
        # Create two real profiles so profile_id FKs are satisfied
        alice = tmp_db.create_profile_with_location(
            name="Alice", birth_date="1991-01-01", birth_time="12:00",
            birth_location_name="Dallas, TX",
            birth_latitude=32.0, birth_longitude=-96.0,
            birth_timezone="America/Chicago",
        )
        bob = tmp_db.create_profile_with_location(
            name="Bob", birth_date="1992-06-15", birth_time="08:00",
            birth_location_name="Austin, TX",
            birth_latitude=30.3, birth_longitude=-97.7,
            birth_timezone="America/Chicago",
        )
        tmp_db.save_event_chart(
            label="p1-event", event_date="2026-01-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Test", chart=SAMPLE_CHART, profile_id=alice.id,
        )
        tmp_db.save_event_chart(
            label="p2-event", event_date="2026-01-02", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Test", chart=SAMPLE_CHART, profile_id=bob.id,
        )
        p1_events = tmp_db.list_event_charts(profile_id=alice.id)
        assert len(p1_events) == 1
        assert p1_events[0].label == "p1-event"


class TestGetEventChartPositions:
    def test_positions_round_trip(self, tmp_db):
        tmp_db.save_event_chart(
            label="round-trip", event_date="2026-02-23", event_time="12:00",
            latitude=32.0, longitude=-96.0, timezone="America/Chicago",
            location_name="Dallas, TX", chart=SAMPLE_CHART,
        )
        ev = tmp_db.get_event_chart_by_label("round-trip")
        positions = tmp_db.get_event_chart_positions(ev.id)

        assert "Sun" in positions["planets"]
        assert "Moon" in positions["planets"]
        assert "1" in positions["houses"]
        assert "ASC" in positions["points"]

        sun = positions["planets"]["Sun"]
        assert sun["sign"] == "Taurus"
        assert isinstance(sun["absolute_position"], float)
        assert sun["house_number"] == 7
        assert sun["is_retrograde"] is False

    def test_retrograde_flag_preserved(self, tmp_db):
        chart = {
            **SAMPLE_CHART,
            "planets": {
                **SAMPLE_CHART["planets"],
                "Mercury": {
                    "degree": 10.0, "sign": "Aries",
                    "house_number": 5, "is_retrograde": True,
                },
            },
        }
        tmp_db.save_event_chart(
            label="retro", event_date="2026-05-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Test", chart=chart,
        )
        ev = tmp_db.get_event_chart_by_label("retro")
        positions = tmp_db.get_event_chart_positions(ev.id)
        assert positions["planets"]["Mercury"]["is_retrograde"] is True


class TestDeleteEventChart:
    def test_delete_existing(self, tmp_db):
        tmp_db.save_event_chart(
            label="to-delete", event_date="2026-01-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Test", chart=SAMPLE_CHART,
        )
        result = tmp_db.delete_event_chart("to-delete")
        assert result is True
        assert tmp_db.list_event_charts() == []

    def test_delete_nonexistent(self, tmp_db):
        result = tmp_db.delete_event_chart("ghost")
        assert result is False

    def test_cascade_deletes_planets(self, tmp_db):
        """Deleting the event should cascade-delete planets/houses/points."""
        from w8s_astro_mcp.models import EventPlanet, EventHouse, EventPoint
        from w8s_astro_mcp.database import get_session

        tmp_db.save_event_chart(
            label="cascade-test", event_date="2026-01-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Test", chart=SAMPLE_CHART,
        )
        ev = tmp_db.get_event_chart_by_label("cascade-test")
        event_id = ev.id

        tmp_db.delete_event_chart("cascade-test")

        with get_session(tmp_db.engine) as session:
            assert session.query(EventPlanet).filter_by(event_id=event_id).count() == 0
            assert session.query(EventHouse).filter_by(event_id=event_id).count() == 0
            assert session.query(EventPoint).filter_by(event_id=event_id).count() == 0


# ============================================================================
# Electional scoring
# ============================================================================

class TestScoreChart:
    def _make_chart(self, moon_deg=15.0, moon_sign="Taurus",
                    sun_sign="Aries", sun_deg=10.0,
                    mercury_retro=False, venus_retro=False,
                    jupiter_house=None, venus_house=None,
                    asc_deg=10.0, asc_sign="Libra"):
        planets = {
            "Sun": {"degree": sun_deg, "sign": sun_sign,
                    "absolute_position": None, "is_retrograde": False,
                    "house_number": 9},
            "Moon": {"degree": moon_deg, "sign": moon_sign,
                     "absolute_position": None, "is_retrograde": False,
                     "house_number": 5},
            "Mercury": {"degree": 12.0, "sign": "Gemini",
                        "is_retrograde": mercury_retro, "house_number": 3},
            "Venus": {"degree": 5.0, "sign": "Taurus",
                      "is_retrograde": venus_retro,
                      "house_number": venus_house or 2},
            "Jupiter": {"degree": 2.0, "sign": "Sagittarius",
                        "is_retrograde": False,
                        "house_number": jupiter_house or 9},
        }
        points = {
            "ASC": {"degree": asc_deg, "sign": asc_sign},
        }
        return {"planets": planets, "houses": {}, "points": points}

    def test_moon_not_void_passes_when_not_near_cusp(self):
        # Moon at 15° Taurus (abs 45°), Sun at 20° Pisces (abs 350°).
        # Sun+60 = 410%360 = 50°, travel from Moon = 5°, orb = 5° → sextile applies.
        chart = self._make_chart(moon_deg=15.0, moon_sign="Taurus",
                                 sun_sign="Pisces", sun_deg=20.0)
        chart["planets"]["Sun"]["absolute_position"] = 350.0
        chart["planets"]["Moon"]["absolute_position"] = 45.0
        met, _ = score_chart(chart, ["moon_not_void"])
        assert "moon_not_void" in met

    def test_moon_not_void_fails_when_near_cusp(self):
        # Moon at 29° Taurus (abs 59°), 1° from Gemini.
        # Sun at 10° Aries (abs 10°): no aspect target lands in Moon's 9° window.
        chart = self._make_chart(moon_deg=29.0, moon_sign="Taurus",
                                 sun_sign="Aries", sun_deg=10.0)
        chart["planets"] = {
            "Sun":  {"degree": 10.0, "sign": "Aries",  "absolute_position": 10.0,  "is_retrograde": False, "house_number": 9},
            "Moon": {"degree": 29.0, "sign": "Taurus", "absolute_position": 59.0,  "is_retrograde": False, "house_number": 5},
            "Mercury": {"degree": 1.0, "sign": "Capricorn", "absolute_position": 271.0, "is_retrograde": False, "house_number": 3},
        }
        met, _ = score_chart(chart, ["moon_not_void"])
        assert "moon_not_void" not in met

    def test_no_retrograde_inner_passes(self):
        chart = self._make_chart(mercury_retro=False, venus_retro=False)
        met, _ = score_chart(chart, ["no_retrograde_inner"])
        assert "no_retrograde_inner" in met

    def test_no_retrograde_inner_fails_mercury_retro(self):
        chart = self._make_chart(mercury_retro=True)
        met, details = score_chart(chart, ["no_retrograde_inner"])
        assert "no_retrograde_inner" not in met
        assert "Mercury" in details["no_retrograde_inner"]

    def test_moon_waxing_passes(self):
        # Moon 90° ahead of Sun = waxing (diff=90°)
        chart = self._make_chart(sun_sign="Aries", sun_deg=0.0,
                                 moon_sign="Cancer", moon_deg=0.0)
        met, _ = score_chart(chart, ["moon_waxing"])
        assert "moon_waxing" in met

    def test_moon_waning_passes(self):
        # Moon 200° ahead of Sun = waning
        chart = self._make_chart(sun_sign="Aries", sun_deg=0.0,
                                 moon_sign="Scorpio", moon_deg=20.0)
        met, _ = score_chart(chart, ["moon_waning"])
        assert "moon_waning" in met

    def test_benefic_angular_passes_venus(self):
        chart = self._make_chart(venus_house=1)
        met, _ = score_chart(chart, ["benefic_angular"])
        assert "benefic_angular" in met

    def test_benefic_angular_passes_jupiter(self):
        chart = self._make_chart(jupiter_house=10)
        met, _ = score_chart(chart, ["benefic_angular"])
        assert "benefic_angular" in met

    def test_benefic_angular_fails_when_cadent(self):
        chart = self._make_chart(venus_house=2, jupiter_house=9)
        met, _ = score_chart(chart, ["benefic_angular"])
        assert "benefic_angular" not in met

    def test_asc_not_late_passes(self):
        chart = self._make_chart(asc_deg=15.0)
        met, _ = score_chart(chart, ["asc_not_late"])
        assert "asc_not_late" in met

    def test_asc_not_late_fails_at_27_plus(self):
        chart = self._make_chart(asc_deg=28.0)
        met, _ = score_chart(chart, ["asc_not_late"])
        assert "asc_not_late" not in met

    def test_multiple_criteria_partial_pass(self):
        # Mercury retrograde → no_retrograde_inner fails
        # Moon at 15° Taurus, Sun at 20° Pisces → sextile applies → not void
        chart = self._make_chart(mercury_retro=True, moon_deg=15.0, moon_sign="Taurus",
                                 sun_sign="Pisces", sun_deg=20.0)
        chart["planets"]["Sun"]["absolute_position"] = 350.0
        chart["planets"]["Moon"]["absolute_position"] = 45.0
        met, details = score_chart(chart, ["moon_not_void", "no_retrograde_inner"])
        assert "moon_not_void" in met
        assert "no_retrograde_inner" not in met

    def test_unknown_criterion_fails_gracefully(self):
        chart = self._make_chart()
        met, details = score_chart(chart, ["nonexistent_criterion"])
        assert "nonexistent_criterion" not in met
        assert "Unknown" in details["nonexistent_criterion"]


# ============================================================================
# Tool handler tests
# ============================================================================

@pytest.mark.asyncio
class TestHandleCastEventChart:
    async def test_missing_date_returns_error(self, tmp_db, mock_ephemeris_engine):
        result = await handle_cast_event_chart(tmp_db, {
            "time": "12:00", "latitude": 32.0, "longitude": -96.0,
            "timezone": "America/Chicago", "location_name": "Dallas",
        })
        assert "error" in result[0].text.lower()

    async def test_missing_coords_returns_error(self, tmp_db, mock_ephemeris_engine):
        result = await handle_cast_event_chart(tmp_db, {
            "date": "2026-02-23", "time": "12:00",
            "timezone": "UTC", "location_name": "Nowhere",
        })
        assert "error" in result[0].text.lower()

    async def test_calculates_without_saving(self, tmp_db, mock_ephemeris_engine):
        result = await handle_cast_event_chart(tmp_db, {
            "date": "2026-02-23", "time": "12:00",
            "latitude": 32.0, "longitude": -96.0,
            "timezone": "America/Chicago", "location_name": "Dallas",
            # No label — should not save
        })
        text = result[0].text
        assert "Sun" in text
        assert "not saved" in text.lower()
        assert tmp_db.list_event_charts() == []

    async def test_saves_when_label_provided(self, tmp_db, mock_ephemeris_engine):
        result = await handle_cast_event_chart(tmp_db, {
            "date": "2026-02-23", "time": "12:00",
            "latitude": 32.0, "longitude": -96.0,
            "timezone": "America/Chicago", "location_name": "Dallas",
            "label": "test-save",
        })
        text = result[0].text
        assert "test-save" in text
        events = tmp_db.list_event_charts()
        assert len(events) == 1
        assert events[0].label == "test-save"

    async def test_duplicate_label_shows_warning(self, tmp_db, mock_ephemeris_engine):
        tmp_db.save_event_chart(
            label="existing", event_date="2026-01-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Test", chart=SAMPLE_CHART,
        )
        result = await handle_cast_event_chart(tmp_db, {
            "date": "2026-02-23", "time": "12:00",
            "latitude": 32.0, "longitude": -96.0,
            "timezone": "America/Chicago", "location_name": "Dallas",
            "label": "existing",
        })
        assert "⚠" in result[0].text or "not saved" in result[0].text.lower()


@pytest.mark.asyncio
class TestHandleListEventCharts:
    async def test_empty_list(self, tmp_db):
        result = await handle_list_event_charts(tmp_db, {})
        assert "no saved" in result[0].text.lower()

    async def test_lists_saved_events(self, tmp_db):
        tmp_db.save_event_chart(
            label="my-event", event_date="2026-03-15", event_time="09:00",
            latitude=51.5, longitude=-0.1, timezone="Europe/London",
            location_name="London, UK", chart=SAMPLE_CHART,
        )
        result = await handle_list_event_charts(tmp_db, {})
        text = result[0].text
        assert "my-event" in text
        assert "2026-03-15" in text
        assert "London" in text
        assert "event:my-event" in text

    async def test_filter_by_profile_id(self, tmp_db):
        alice = tmp_db.create_profile_with_location(
            name="Alice", birth_date="1991-01-01", birth_time="12:00",
            birth_location_name="Dallas, TX",
            birth_latitude=32.0, birth_longitude=-96.0,
            birth_timezone="America/Chicago",
        )
        bob = tmp_db.create_profile_with_location(
            name="Bob", birth_date="1992-06-15", birth_time="08:00",
            birth_location_name="Austin, TX",
            birth_latitude=30.3, birth_longitude=-97.7,
            birth_timezone="America/Chicago",
        )
        tmp_db.save_event_chart(
            label="p1", event_date="2026-01-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="A", chart=SAMPLE_CHART, profile_id=alice.id,
        )
        tmp_db.save_event_chart(
            label="p2", event_date="2026-01-02", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="B", chart=SAMPLE_CHART, profile_id=bob.id,
        )
        result = await handle_list_event_charts(tmp_db, {"profile_id": alice.id})
        text = result[0].text
        assert "p1" in text
        assert "p2" not in text


@pytest.mark.asyncio
class TestHandleDeleteEventChart:
    async def test_requires_confirm_true(self, tmp_db):
        result = await handle_delete_event_chart(tmp_db, {
            "label": "anything", "confirm": False
        })
        assert "confirm" in result[0].text.lower()

    async def test_requires_label(self, tmp_db):
        result = await handle_delete_event_chart(tmp_db, {"confirm": True})
        assert "error" in result[0].text.lower()

    async def test_deletes_existing(self, tmp_db):
        tmp_db.save_event_chart(
            label="del-me", event_date="2026-01-01", event_time="12:00",
            latitude=0.0, longitude=0.0, timezone="UTC",
            location_name="Test", chart=SAMPLE_CHART,
        )
        result = await handle_delete_event_chart(tmp_db, {
            "label": "del-me", "confirm": True
        })
        assert "del-me" in result[0].text
        assert "✓" in result[0].text
        assert tmp_db.list_event_charts() == []

    async def test_not_found(self, tmp_db):
        result = await handle_delete_event_chart(tmp_db, {
            "label": "ghost", "confirm": True
        })
        assert "not found" in result[0].text.lower()


@pytest.mark.asyncio
class TestHandleFindElectionalWindows:
    def _make_mock_chart(self, moon_deg=15.0, mercury_retro=False):
        return {
            "planets": {
                "Sun": {"degree": 0.0, "sign": "Aries",
                        "absolute_position": 0.0, "is_retrograde": False, "house_number": 9},
                "Moon": {"degree": moon_deg, "sign": "Taurus",
                         "absolute_position": 30.0 + moon_deg, "is_retrograde": False, "house_number": 5},
                "Mercury": {"degree": 5.0, "sign": "Gemini",
                            "is_retrograde": mercury_retro, "house_number": 3},
                "Venus": {"degree": 5.0, "sign": "Taurus",
                          "is_retrograde": False, "house_number": 1},
                "Jupiter": {"degree": 2.0, "sign": "Aquarius",
                            "is_retrograde": False, "house_number": 10},
                "Mars": {"degree": 10.0, "sign": "Leo",
                         "is_retrograde": False, "house_number": 8},
                "Saturn": {"degree": 3.0, "sign": "Libra",
                           "is_retrograde": False, "house_number": 11},
                "Uranus": {"degree": 22.0, "sign": "Pisces",
                           "is_retrograde": False, "house_number": 4},
                "Neptune": {"degree": 24.0, "sign": "Aquarius",
                            "is_retrograde": False, "house_number": 4},
                "Pluto": {"degree": 3.0, "sign": "Capricorn",
                          "is_retrograde": False, "house_number": 3},
            },
            "houses": {"1": {"degree": 10.0, "sign": "Scorpio"}},
            "points": {"ASC": {"degree": 10.0, "sign": "Scorpio"}},
            "metadata": {},
        }

    async def test_missing_required_fields(self, tmp_db):
        result = await handle_find_electional_windows(tmp_db, {})
        assert "error" in result[0].text.lower()

    async def test_window_too_large(self, tmp_db):
        result = await handle_find_electional_windows(tmp_db, {
            "start_date": "2026-01-01", "end_date": "2026-06-01",
            "latitude": 32.0, "longitude": -96.0,
            "timezone": "America/Chicago", "location_name": "Dallas",
            "criteria": ["moon_not_void"],
        })
        assert "90 days" in result[0].text

    async def test_returns_candidates(self, tmp_db):
        chart = self._make_mock_chart()
        import types, sys
        fake_mod = types.ModuleType("w8s_astro_mcp.utils.ephemeris")
        class FakeEphemerisError(Exception): pass
        class FakeEngine:
            def get_chart(self, **kwargs): return chart
        fake_mod.EphemerisEngine = FakeEngine
        fake_mod.EphemerisError = FakeEphemerisError
        key = "w8s_astro_mcp.utils.ephemeris"
        orig = sys.modules.get(key)
        sys.modules[key] = fake_mod
        try:
            result = await handle_find_electional_windows(tmp_db, {
                "start_date": "2026-03-01", "end_date": "2026-03-03",
                "latitude": 32.0, "longitude": -96.0,
                "timezone": "America/Chicago", "location_name": "Dallas",
                "criteria": ["moon_not_void", "benefic_angular"],
                "interval_minutes": 360,
                "max_results": 5,
            })
        finally:
            if orig is None: sys.modules.pop(key, None)
            else: sys.modules[key] = orig
        text = result[0].text
        assert "Electional Windows" in text
        assert "✓" in text

    async def test_no_candidates_message(self, tmp_db):
        # Use a chart where Mercury is retrograde — no_retrograde_inner will always fail
        chart = self._make_mock_chart(mercury_retro=True)
        import types, sys
        fake_mod = types.ModuleType("w8s_astro_mcp.utils.ephemeris")
        class FakeEphemerisError(Exception): pass
        class FakeEngine:
            def get_chart(self, **kwargs): return chart
        fake_mod.EphemerisEngine = FakeEngine
        fake_mod.EphemerisError = FakeEphemerisError
        key = "w8s_astro_mcp.utils.ephemeris"
        orig = sys.modules.get(key)
        sys.modules[key] = fake_mod
        try:
            result = await handle_find_electional_windows(tmp_db, {
                "start_date": "2026-03-01", "end_date": "2026-03-02",
                "latitude": 32.0, "longitude": -96.0,
                "timezone": "America/Chicago", "location_name": "Dallas",
                "criteria": ["no_retrograde_inner"],
                "interval_minutes": 360,
            })
        finally:
            if orig is None: sys.modules.pop(key, None)
            else: sys.modules[key] = orig
        assert "no candidates" in result[0].text.lower()


# ============================================================================
# EVENT_TOOL_NAMES registry
# ============================================================================

class TestEventToolNames:
    def test_all_expected_tools_registered(self):
        expected = {
            "cast_event_chart",
            "list_event_charts",
            "delete_event_chart",
            "find_electional_windows",
        }
        assert EVENT_TOOL_NAMES == expected
