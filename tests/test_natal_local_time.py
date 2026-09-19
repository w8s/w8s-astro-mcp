"""Natal charts are calculated from the birth time converted from local time to UT.

Before v0.13.1 the stored birth time was handed to the ephemeris as if it were already UT, so every
chart was off by the birth location's UTC offset (wrong Ascendant, MC, houses and Moon).
"""

import pytest

from w8s_astro_mcp.database import initialize_database
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper
from w8s_astro_mcp.utils.ephemeris import EphemerisEngine, EphemerisError

# Reference chart, cross-checked against an independent chart site (astro-charts.com):
# 1981-05-06 00:50 local time (CDT, UTC-5) in St. Louis -> Capricorn rising, Scorpio MC.
REFERENCE = dict(
    name="Reference",
    birth_date="1981-05-06",
    birth_time="00:50",
    birth_location_name="St. Louis, MO",
    birth_latitude=38.627,
    birth_longitude=-90.199,
    birth_timezone="America/Chicago",
)


@pytest.fixture
def srv_and_db(tmp_path):
    import w8s_astro_mcp.server as srv

    path = tmp_path / "astro.db"
    initialize_database(path, echo=False)          # schema + seeded house systems
    db = DatabaseHelper(db_path=str(path))
    previous = srv.db_helper
    srv.db_helper = db
    yield srv, db
    srv.db_helper = previous


def _natal(srv, db, **overrides):
    profile = db.create_profile_with_location(**{**REFERENCE, **overrides})
    return profile, srv.get_natal_chart_data(profile_id=profile.id)


def test_reference_chart_matches_independent_site(srv_and_db):
    srv, db = srv_and_db
    _, chart = _natal(srv, db)

    asc, mc, moon = chart["points"]["Ascendant"], chart["points"]["MC"], chart["planets"]["Moon"]
    assert asc["sign"] == "Capricorn"
    assert asc["degree"] == pytest.approx(20.95, abs=0.05)   # 20°57'
    assert mc["sign"] == "Scorpio"
    assert mc["degree"] == pytest.approx(13.77, abs=0.05)    # 13°46'
    assert moon["sign"] == "Gemini"
    assert moon["degree"] == pytest.approx(14.97, abs=0.05)  # 14°58'


def test_treating_local_time_as_ut_would_give_a_different_chart(srv_and_db):
    """Guard: the old behaviour gives Scorpio rising, so the test above can tell them apart."""
    naive = EphemerisEngine().get_chart(38.627, -90.199, "1981-05-06", "00:50")
    assert naive["points"]["Ascendant"]["sign"] == "Scorpio"


def test_profile_keeps_the_local_birth_time(srv_and_db):
    srv, db = srv_and_db
    profile, chart = _natal(srv, db)
    assert db.get_profile_by_id(profile.id).birth_time == "00:50"
    assert chart["metadata"]["time"] == "00:50"


@pytest.mark.parametrize(
    "birth, lat, lon, ut_date, ut_time",
    [
        (("1983-08-27", "09:52", "America/Los_Angeles"), 34.90, -117.02, "1983-08-27", "16:52"),
        (("2009-12-10", "14:48", "America/New_York"), 40.44, -79.96, "2009-12-10", "19:48"),
        (("2000-01-15", "22:30", "America/Los_Angeles"), 34.05, -118.24, "2000-01-16", "06:30"),  # UT is next day
        (("2001-06-01", "01:00", "Asia/Tokyo"), 35.68, 139.69, "2001-05-31", "16:00"),           # UT is previous day
    ],
)
def test_stored_chart_equals_a_direct_calculation_at_the_converted_ut(srv_and_db, birth, lat, lon, ut_date, ut_time):
    srv, db = srv_and_db
    date, time, tz = birth
    _, chart = _natal(
        srv, db, birth_date=date, birth_time=time, birth_timezone=tz,
        birth_latitude=lat, birth_longitude=lon, birth_location_name="Somewhere",
    )
    expected = EphemerisEngine().get_chart(lat, lon, ut_date, ut_time, "P")

    for point in ("Ascendant", "MC"):
        assert chart["points"][point]["sign"] == expected["points"][point]["sign"]
        assert chart["points"][point]["degree"] == pytest.approx(expected["points"][point]["degree"], abs=0.02)
    for planet, position in expected["planets"].items():
        assert chart["planets"][planet]["sign"] == position["sign"]
        assert chart["planets"][planet]["degree"] == pytest.approx(position["degree"], abs=0.02)
    for house, position in expected["houses"].items():
        assert chart["houses"][house]["sign"] == position["sign"]


def test_unknown_timezone_gives_a_clear_error(srv_and_db):
    srv, db = srv_and_db
    profile = db.create_profile_with_location(**{**REFERENCE, "birth_timezone": "Mars/Olympus"})
    with pytest.raises(EphemerisError, match="timezone"):
        srv.get_natal_chart_data(profile_id=profile.id)


def test_editing_the_birth_time_recalculates_with_the_conversion(srv_and_db):
    srv, db = srv_and_db
    profile, before = _natal(srv, db)
    assert before["points"]["Ascendant"]["sign"] == "Capricorn"

    db.update_profile_field(profile.id, "birth_time", "05:50")   # invalidates the cached chart
    after = srv.get_natal_chart_data(profile_id=profile.id)

    expected = EphemerisEngine().get_chart(38.627, -90.199, "1981-05-06", "10:50", "P")   # 05:50 CDT = 10:50 UT
    assert after["points"]["Ascendant"]["sign"] == expected["points"]["Ascendant"]["sign"]
    assert after["points"]["Ascendant"]["degree"] == pytest.approx(expected["points"]["Ascendant"]["degree"], abs=0.02)
    assert after["points"]["Ascendant"]["sign"] != before["points"]["Ascendant"]["sign"]
