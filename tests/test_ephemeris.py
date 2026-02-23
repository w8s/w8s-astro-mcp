"""Unit tests for the pysweph-based ephemeris engine.

Tests are organized from smallest unit (helpers) up to full chart output,
verifying the output structure is backward-compatible with the old swetest parser.
"""

import pytest
from unittest.mock import patch, MagicMock
from w8s_astro_mcp.utils.ephemeris import EphemerisEngine, EphemerisError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Return a default EphemerisEngine (Moshier mode)."""
    return EphemerisEngine()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    """EphemerisEngine initialization."""

    def test_default_init(self):
        """Engine initializes without arguments."""
        e = EphemerisEngine()
        assert e is not None

    def test_ephe_path_none_by_default(self):
        """Default ephemeris path is None (Moshier)."""
        e = EphemerisEngine()
        assert e.ephe_path is None

    def test_ephe_path_stored(self, tmp_path):
        """Custom ephe_path is stored on the instance."""
        e = EphemerisEngine(ephe_path=str(tmp_path))
        assert e.ephe_path == str(tmp_path)


# ---------------------------------------------------------------------------
# Julian Day conversion
# ---------------------------------------------------------------------------

class TestJulianDay:
    """_to_jd() converts calendar date+time to Julian Day number."""

    def test_known_date(self, engine):
        """2000-01-01 12:00 UT = JD 2451545.0 (J2000.0 epoch)."""
        jd = engine._to_jd(2000, 1, 1, 12.0)
        assert jd == pytest.approx(2451545.0, abs=0.001)

    def test_hour_decimal(self, engine):
        """12:30 converts to 12.5 hours."""
        jd_noon = engine._to_jd(2026, 2, 3, 12.0)
        jd_half = engine._to_jd(2026, 2, 3, 12.5)
        assert jd_half > jd_noon
        assert jd_half - jd_noon == pytest.approx(0.5 / 24, abs=1e-6)

    def test_time_string_parsing(self, engine):
        """_parse_time() converts 'HH:MM' to decimal hours."""
        assert engine._parse_time("12:00") == pytest.approx(12.0)
        assert engine._parse_time("00:00") == pytest.approx(0.0)
        assert engine._parse_time("23:30") == pytest.approx(23.5)
        assert engine._parse_time("06:15") == pytest.approx(6.25)

    def test_invalid_time_string(self, engine):
        """Invalid time string raises EphemerisError."""
        with pytest.raises(EphemerisError, match="time"):
            engine._parse_time("25:00")
        with pytest.raises(EphemerisError, match="time"):
            engine._parse_time("12:60")
        with pytest.raises(EphemerisError, match="time"):
            engine._parse_time("not-a-time")


# ---------------------------------------------------------------------------
# Sign and degree helpers
# ---------------------------------------------------------------------------

class TestLongitudeToSign:
    """_longitude_to_sign_info() converts absolute 0–360° to sign metadata."""

    CASES = [
        (0.0,   "Aries",       0.0),
        (15.0,  "Aries",       15.0),
        (29.99, "Aries",       29.99),
        (30.0,  "Taurus",      0.0),
        (45.0,  "Taurus",      15.0),
        (60.0,  "Gemini",      0.0),
        (90.0,  "Cancer",      0.0),
        (120.0, "Leo",         0.0),
        (150.0, "Virgo",       0.0),
        (180.0, "Libra",       0.0),
        (210.0, "Scorpio",     0.0),
        (240.0, "Sagittarius", 0.0),
        (270.0, "Capricorn",   0.0),
        (300.0, "Aquarius",    0.0),
        (314.66,"Aquarius",    14.66),
        (330.0, "Pisces",      0.0),
        (359.99,"Pisces",      29.99),
    ]

    @pytest.mark.parametrize("longitude,expected_sign,expected_degree", CASES)
    def test_sign_and_degree(self, engine, longitude, expected_sign, expected_degree):
        result = engine._longitude_to_sign_info(longitude)
        assert result["sign"] == expected_sign
        assert result["degree"] == pytest.approx(expected_degree, abs=0.01)
        assert result["absolute_position"] == pytest.approx(longitude, abs=0.001)

    def test_includes_formatted(self, engine):
        """Result includes a non-empty 'formatted' string."""
        result = engine._longitude_to_sign_info(314.66)
        assert "formatted" in result
        assert "°" in result["formatted"]

    def test_formatted_degrees_and_minutes(self, engine):
        """14°39' at 314.66°."""
        result = engine._longitude_to_sign_info(314.66)
        assert result["formatted"].startswith("14°39'")

    def test_sign_boundary_30(self, engine):
        """Exactly 30° is the first degree of the next sign, not 30° of the previous."""
        result = engine._longitude_to_sign_info(30.0)
        assert result["sign"] == "Taurus"
        assert result["degree"] == pytest.approx(0.0, abs=0.001)

    def test_sign_boundary_360(self, engine):
        """360° wraps back to 0° Aries."""
        result = engine._longitude_to_sign_info(360.0)
        assert result["sign"] == "Aries"


# ---------------------------------------------------------------------------
# Retrograde detection
# ---------------------------------------------------------------------------

class TestRetrograde:
    """is_retrograde detection from speed value."""

    def test_negative_speed_is_retrograde(self, engine):
        assert engine._is_retrograde(-0.001) is True
        assert engine._is_retrograde(-1.5) is True

    def test_positive_speed_is_direct(self, engine):
        assert engine._is_retrograde(1.0) is False
        assert engine._is_retrograde(0.0) is False


# ---------------------------------------------------------------------------
# House system code
# ---------------------------------------------------------------------------

class TestHouseSystemCode:
    """_house_system_bytes() returns the correct bytes literal."""

    def test_placidus(self, engine):
        assert engine._house_system_bytes("P") == b"P"
        assert engine._house_system_bytes("Placidus") == b"P"

    def test_whole_sign(self, engine):
        assert engine._house_system_bytes("W") == b"W"

    def test_equal(self, engine):
        assert engine._house_system_bytes("E") == b"E"

    def test_unknown_code_defaults_to_placidus(self, engine):
        """Unknown codes fall back to Placidus with a warning (no exception)."""
        result = engine._house_system_bytes("Z")
        assert result == b"P"


# ---------------------------------------------------------------------------
# Full chart output structure
# ---------------------------------------------------------------------------

class TestGetChart:
    """get_chart() returns the canonical output dict."""

    def test_returns_required_keys(self, engine):
        result = engine.get_chart(
            latitude=38.637,
            longitude=-90.263,
            date_str="2026-02-03",
            time_str="12:00"
        )
        assert "planets" in result
        assert "houses" in result
        assert "points" in result
        assert "metadata" in result

    def test_all_planets_present(self, engine):
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        expected = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        for planet in expected:
            assert planet in result["planets"], f"Missing planet: {planet}"

    def test_planet_fields(self, engine):
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        sun = result["planets"]["Sun"]
        assert "sign" in sun
        assert "degree" in sun
        assert "formatted" in sun
        assert "absolute_position" in sun
        assert "is_retrograde" in sun

    def test_all_houses_present(self, engine):
        """House keys are strings '1' through '12'."""
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        for h in range(1, 13):
            assert str(h) in result["houses"], f"Missing house: {h}"

    def test_house_fields(self, engine):
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        house1 = result["houses"]["1"]
        assert "sign" in house1
        assert "degree" in house1
        assert "formatted" in house1
        assert "absolute_position" in house1

    def test_points_present(self, engine):
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        assert "Ascendant" in result["points"]
        assert "MC" in result["points"]

    def test_metadata_fields(self, engine):
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        meta = result["metadata"]
        assert meta["date"] == "2026-02-03"
        assert meta["time"] == "12:00:00"
        assert meta["latitude"] == pytest.approx(38.637)
        assert meta["longitude"] == pytest.approx(-90.263)
        assert "house_system" in meta
        assert "ephemeris" in meta

    def test_metadata_ephemeris_moshier(self, engine):
        """Default mode reports 'moshier' in metadata."""
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        assert result["metadata"]["ephemeris"] == "moshier"

    def test_sun_position_feb_2026(self, engine):
        """Sun should be in Aquarius on 2026-02-03."""
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        assert result["planets"]["Sun"]["sign"] == "Aquarius"

    def test_date_defaults_to_today(self, engine):
        """Calling with no date_str does not raise."""
        result = engine.get_chart(38.637, -90.263)
        assert "planets" in result

    def test_invalid_date_raises(self, engine):
        with pytest.raises(EphemerisError, match="date"):
            engine.get_chart(38.637, -90.263, date_str="not-a-date")

    def test_degree_values_in_range(self, engine):
        """Degree within sign is always 0–<30."""
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        for name, planet in result["planets"].items():
            assert 0.0 <= planet["degree"] < 30.0, \
                f"{name} degree {planet['degree']} out of range"

    def test_absolute_position_in_range(self, engine):
        """Absolute position is always 0–<360."""
        result = engine.get_chart(38.637, -90.263, "2026-02-03", "12:00")
        for name, planet in result["planets"].items():
            assert 0.0 <= planet["absolute_position"] < 360.0, \
                f"{name} absolute_position {planet['absolute_position']} out of range"


# ---------------------------------------------------------------------------
# get_chart() is an alias for backward compatibility
# ---------------------------------------------------------------------------

class TestGetTransitsAlias:
    """get_transits() is a backward-compatible alias for get_chart()."""

    def test_get_transits_alias(self, engine):
        result = engine.get_transits(38.637, -90.263, "2026-02-03", "12:00")
        assert "planets" in result
        assert "houses" in result


# ---------------------------------------------------------------------------
# Ephemeris path and mode
# ---------------------------------------------------------------------------

class TestEphemerisMode:
    """Ephemeris mode selection via ephe_path."""

    def test_moshier_mode_when_path_is_none(self):
        e = EphemerisEngine(ephe_path=None)
        assert e.get_mode() == "moshier"

    def test_sweph_mode_when_path_is_set(self, tmp_path):
        e = EphemerisEngine(ephe_path=str(tmp_path))
        assert e.get_mode() == "sweph"
