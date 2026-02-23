"""Tests for connection chart calculation engine.

Tests cover:
- circular_mean_degrees: wraparound, identical, opposite, N-way, edge cases
- degrees_to_sign_components: all 12 signs, boundaries, floating point safety
- calculate_composite_positions: two-way, N-way, missing planets, error cases
- calculate_davison_midpoint: two-way, N-way, cross-midnight, error cases
- enrich_natal_chart_for_composite: adds missing absolute_position
"""

import math
import pytest
from unittest.mock import MagicMock

from w8s_astro_mcp.utils.connection_calculator import (
    circular_mean_degrees,
    degrees_to_sign_components,
    calculate_composite_positions,
    calculate_davison_midpoint,
    enrich_natal_chart_for_composite,
)


# =============================================================================
# HELPERS
# =============================================================================

def near(a: float, b: float, tol: float = 0.001) -> bool:
    """True if a and b are within tol of each other on a circle (0-360)."""
    diff = abs(a % 360.0 - b % 360.0)
    return min(diff, 360.0 - diff) < tol


def make_chart(planet_positions: dict, house_positions: dict = None, point_positions: dict = None):
    """Build a minimal natal-chart-like dict for composite tests."""
    planets = {name: {"absolute_position": pos} for name, pos in planet_positions.items()}
    houses = {k: {"absolute_position": v} for k, v in (house_positions or {}).items()}
    points = {k: {"absolute_position": v} for k, v in (point_positions or {}).items()}
    return {"planets": planets, "houses": houses, "points": points}


def make_profile(birth_date: str, birth_time: str):
    """Build a minimal mock Profile."""
    p = MagicMock()
    p.birth_date = birth_date
    p.birth_time = birth_time
    return p


def make_location(latitude: float, longitude: float, timezone: str = "UTC"):
    """Build a minimal mock Location."""
    loc = MagicMock()
    loc.latitude = latitude
    loc.longitude = longitude
    loc.timezone = timezone
    return loc


# =============================================================================
# circular_mean_degrees
# =============================================================================

class TestCircularMeanDegrees:
    """Tests for circular_mean_degrees()."""

    def test_identical_angles(self):
        """Mean of identical angles should return that angle."""
        assert near(circular_mean_degrees([90.0, 90.0]), 90.0)
        assert near(circular_mean_degrees([0.0, 0.0, 0.0]), 0.0)
        assert near(circular_mean_degrees([270.0, 270.0]), 270.0)

    def test_wraparound_simple(self):
        """350° and 10° should average to 0° (not 180°)."""
        result = circular_mean_degrees([350.0, 10.0])
        assert near(result, 0.0)

    def test_wraparound_asymmetric(self):
        """355° and 5° should average to 0°."""
        result = circular_mean_degrees([355.0, 5.0])
        assert near(result, 0.0)

    def test_wraparound_large_gap(self):
        """340° and 20° should average to 0°."""
        result = circular_mean_degrees([340.0, 20.0])
        assert near(result, 0.0)

    def test_simple_average(self):
        """30° and 90° should average to 60°."""
        result = circular_mean_degrees([30.0, 90.0])
        assert near(result, 60.0)

    def test_three_way_average(self):
        """0°, 120°, 240° are equally spaced — mean is undefined but near 0°."""
        # The result magnitude is near 0 (vectors cancel), direction arbitrary
        # We just verify it doesn't crash and returns a valid angle
        result = circular_mean_degrees([0.0, 120.0, 240.0])
        assert 0.0 <= result < 360.0

    def test_n_way_same_angle(self):
        """10 identical angles should return that angle."""
        result = circular_mean_degrees([45.0] * 10)
        assert near(result, 45.0)

    def test_single_angle(self):
        """Single angle should return itself."""
        result = circular_mean_degrees([180.0])
        assert near(result, 180.0)

    def test_empty_raises(self):
        """Empty list should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            circular_mean_degrees([])

    def test_result_always_in_range(self):
        """Result should always be in [0, 360)."""
        test_cases = [
            [0.0, 360.0],
            [359.9, 0.1],
            [180.0, 180.0],
            [0.0, 0.0],
        ]
        for angles in test_cases:
            result = circular_mean_degrees(angles)
            assert 0.0 <= result < 360.0 or abs(result - 360.0) < 0.001

    def test_opposite_angles_magnitude(self):
        """Opposite angles (90° and 270°) produce near-zero vector magnitude."""
        # The mean direction is arbitrary when vectors cancel, but shouldn't crash
        result = circular_mean_degrees([90.0, 270.0])
        assert 0.0 <= result < 360.0 or abs(result - 360.0) < 0.001

    def test_all_12_signs_midpoints(self):
        """Average midpoints of adjacent signs should be their shared boundary."""
        # Aries midpoint (15°) and Taurus midpoint (45°) → 30° (boundary)
        result = circular_mean_degrees([15.0, 45.0])
        assert near(result, 30.0)


# =============================================================================
# degrees_to_sign_components
# =============================================================================

class TestDegreesToSignComponents:
    """Tests for degrees_to_sign_components()."""

    SIGN_BOUNDARIES = [
        (0.0, "Aries"),
        (30.0, "Taurus"),
        (60.0, "Gemini"),
        (90.0, "Cancer"),
        (120.0, "Leo"),
        (150.0, "Virgo"),
        (180.0, "Libra"),
        (210.0, "Scorpio"),
        (240.0, "Sagittarius"),
        (270.0, "Capricorn"),
        (300.0, "Aquarius"),
        (330.0, "Pisces"),
    ]

    def test_all_12_sign_starts(self):
        """Each sign should start at its expected boundary degree."""
        for absolute, expected_sign in self.SIGN_BOUNDARIES:
            sign, degree, minutes, seconds = degrees_to_sign_components(absolute)
            assert sign == expected_sign, f"{absolute}° → expected {expected_sign}, got {sign}"
            assert degree == 0

    def test_aries_midpoint(self):
        """15° Aries."""
        sign, degree, minutes, seconds = degrees_to_sign_components(15.0)
        assert sign == "Aries"
        assert degree == 15
        assert minutes == 0

    def test_taurus_midpoint(self):
        """15° Taurus = 45° absolute."""
        sign, degree, minutes, seconds = degrees_to_sign_components(45.0)
        assert sign == "Taurus"
        assert degree == 15

    def test_pisces_end(self):
        """359.9° should be Pisces."""
        sign, *_ = degrees_to_sign_components(359.9)
        assert sign == "Pisces"

    def test_minutes_calculation(self):
        """30.5° absolute = 0°30' Taurus."""
        sign, degree, minutes, seconds = degrees_to_sign_components(30.5)
        assert sign == "Taurus"
        assert degree == 0
        assert minutes == 30

    def test_seconds_calculation(self):
        """30° + 30' + 30" = 30.508333...° absolute."""
        absolute = 30.0 + 30 / 60 + 30 / 3600
        sign, degree, minutes, seconds = degrees_to_sign_components(absolute)
        assert sign == "Taurus"
        assert degree == 0
        assert minutes == 30
        assert abs(seconds - 30.0) < 0.01

    def test_wraparound_360(self):
        """360.0° should wrap to Aries."""
        sign, degree, *_ = degrees_to_sign_components(360.0)
        assert sign == "Aries"
        assert degree == 0

    def test_floating_point_boundary(self):
        """59.9999999999° should be Taurus, not Gemini."""
        sign, *_ = degrees_to_sign_components(59.9999999999)
        assert sign == "Taurus"

    def test_exact_boundary_60(self):
        """Exactly 60.0° should be Gemini (boundary belongs to next sign)."""
        sign, degree, *_ = degrees_to_sign_components(60.0)
        assert sign == "Gemini"
        assert degree == 0

    def test_all_components_non_negative(self):
        """All returned components should be non-negative."""
        for angle in [0.0, 15.0, 45.5, 179.99, 270.0, 359.9]:
            sign, degree, minutes, seconds = degrees_to_sign_components(angle)
            assert degree >= 0
            assert minutes >= 0
            assert seconds >= 0.0


# =============================================================================
# calculate_composite_positions
# =============================================================================

class TestCalculateCompositePositions:
    """Tests for calculate_composite_positions()."""

    def test_two_charts_simple_average(self):
        """Average of 30° and 90° Sun should be ~60° (Gemini)."""
        charts = [
            make_chart({"Sun": 30.0}),
            make_chart({"Sun": 90.0}),
        ]
        result = calculate_composite_positions(charts)
        assert near(result["planets"]["Sun"]["absolute_position"], 60.0)
        assert result["planets"]["Sun"]["sign"] == "Gemini"

    def test_wraparound_planets(self):
        """Sun at 350° and 10° should composite to ~0° (Aries)."""
        charts = [
            make_chart({"Sun": 350.0}),
            make_chart({"Sun": 10.0}),
        ]
        result = calculate_composite_positions(charts)
        assert near(result["planets"]["Sun"]["absolute_position"], 0.0)
        assert result["planets"]["Sun"]["sign"] == "Aries"

    def test_three_way_composite(self):
        """Three charts — Sun at 0°, 120°, 240° should average near 0°."""
        charts = [
            make_chart({"Sun": 0.0}),
            make_chart({"Sun": 120.0}),
            make_chart({"Sun": 240.0}),
        ]
        result = calculate_composite_positions(charts)
        # Vectors cancel — result should be a valid angle (no crash)
        assert "Sun" in result["planets"]

    def test_n_way_identical_positions(self):
        """10 charts all with Sun at 45° should produce 45° composite."""
        charts = [make_chart({"Sun": 45.0}) for _ in range(10)]
        result = calculate_composite_positions(charts)
        assert near(result["planets"]["Sun"]["absolute_position"], 45.0)

    def test_missing_planet_excluded(self):
        """Planet missing from any chart is excluded from composite."""
        chart_a = make_chart({"Sun": 30.0, "Moon": 60.0})
        chart_b = make_chart({"Sun": 90.0})  # No Moon
        result = calculate_composite_positions([chart_a, chart_b])
        assert "Sun" in result["planets"]
        assert "Moon" not in result["planets"]

    def test_houses_averaged(self):
        """Houses should also be circularly averaged."""
        charts = [
            make_chart({"Sun": 0.0}, house_positions={"1": 0.0, "7": 180.0}),
            make_chart({"Sun": 0.0}, house_positions={"1": 60.0, "7": 240.0}),
        ]
        result = calculate_composite_positions(charts)
        assert near(result["houses"]["1"]["absolute_position"], 30.0)
        assert near(result["houses"]["7"]["absolute_position"], 210.0)

    def test_points_averaged(self):
        """Points (ASC, MC) should be circularly averaged."""
        charts = [
            make_chart({"Sun": 0.0}, point_positions={"ASC": 10.0, "MC": 100.0}),
            make_chart({"Sun": 0.0}, point_positions={"ASC": 30.0, "MC": 120.0}),
        ]
        result = calculate_composite_positions(charts)
        assert near(result["points"]["ASC"]["absolute_position"], 20.0)

    def test_result_has_sign_components(self):
        """Each planet entry should have sign, degree, minutes, seconds."""
        charts = [make_chart({"Sun": 45.0}), make_chart({"Sun": 45.0})]
        result = calculate_composite_positions(charts)
        sun = result["planets"]["Sun"]
        assert "sign" in sun
        assert "degree" in sun
        assert "minutes" in sun
        assert "seconds" in sun
        assert "absolute_position" in sun

    def test_single_chart_raises(self):
        """Fewer than 2 charts should raise ValueError."""
        with pytest.raises(ValueError, match="2"):
            calculate_composite_positions([make_chart({"Sun": 0.0})])

    def test_empty_raises(self):
        """Empty list should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_composite_positions([])

    def test_multiple_planets(self):
        """Should process all planets correctly."""
        planet_positions = {
            "Sun": 15.0, "Moon": 45.0, "Mercury": 75.0,
            "Venus": 105.0, "Mars": 135.0,
        }
        chart_a = make_chart(planet_positions)
        chart_b = make_chart(planet_positions)  # Same → composite = same
        result = calculate_composite_positions([chart_a, chart_b])
        for planet, pos in planet_positions.items():
            assert near(result["planets"][planet]["absolute_position"], pos)

    def test_house_keys_are_strings(self):
        """House keys in result should be strings ('1'-'12')."""
        charts = [
            make_chart({"Sun": 0.0}, house_positions={"1": 0.0}),
            make_chart({"Sun": 0.0}, house_positions={"1": 60.0}),
        ]
        result = calculate_composite_positions(charts)
        assert "1" in result["houses"]
        assert 1 not in result["houses"]

    def test_absolute_position_in_range(self):
        """All absolute positions should be 0-360."""
        charts = [make_chart({"Sun": 355.0}), make_chart({"Sun": 5.0})]
        result = calculate_composite_positions(charts)
        pos = result["planets"]["Sun"]["absolute_position"]
        assert 0.0 <= pos < 360.0 or abs(pos - 360.0) < 0.001


# =============================================================================
# calculate_davison_midpoint
# =============================================================================

class TestCalculateDavisonMidpoint:
    """Tests for calculate_davison_midpoint()."""

    def test_same_day_different_times_utc(self):
        """Two profiles born same day UTC, midnight and noon → midpoint is 6am UTC."""
        profiles = [
            make_profile("2000-01-01", "00:00"),
            make_profile("2000-01-01", "12:00"),
        ]
        locations = [make_location(0.0, 0.0, "UTC"), make_location(0.0, 0.0, "UTC")]
        result = calculate_davison_midpoint(profiles, locations)
        assert result["date"] == "2000-01-01"
        assert result["time"] == "06:00"

    def test_timezone_conversion_affects_midpoint(self):
        """Birth times are local clock — timezone conversion must happen before averaging.

        Person A: born 2000-01-01 00:00 UTC    → 2000-01-01 00:00 UTC
        Person B: born 2000-01-01 00:00 CST    → 2000-01-01 06:00 UTC (CST = UTC-6)
        Midpoint: 2000-01-01 03:00 UTC

        Without timezone conversion (the old bug), both would be treated as UTC,
        giving a midpoint of 2000-01-01 00:00 — 3 hours wrong.
        """
        profiles = [
            make_profile("2000-01-01", "00:00"),
            make_profile("2000-01-01", "00:00"),
        ]
        locations = [
            make_location(0.0, 0.0, "UTC"),
            make_location(29.95, -90.07, "America/Chicago"),  # CST = UTC-6
        ]
        result = calculate_davison_midpoint(profiles, locations)
        # CST midnight = UTC 06:00, so midpoint of UTC 00:00 and UTC 06:00 = UTC 03:00
        assert result["date"] == "2000-01-01"
        assert result["time"] == "03:00"

    def test_same_local_time_different_zones_not_same_midpoint(self):
        """Two people born at the same local time in different timezones
        are NOT born at the same moment — midpoint should reflect the UTC difference."""
        profiles = [
            make_profile("2000-06-15", "12:00"),
            make_profile("2000-06-15", "12:00"),
        ]
        locations = [
            make_location(51.5, 0.0, "Europe/London"),    # BST = UTC+1 in June
            make_location(40.7, -74.0, "America/New_York"),  # EDT = UTC-4 in June
        ]
        result = calculate_davison_midpoint(profiles, locations)
        # London noon = UTC 11:00; New York noon = UTC 16:00; midpoint = UTC 13:30
        assert result["date"] == "2000-06-15"
        assert result["time"] == "13:30"

    def test_different_years_exact(self):
        """Born exactly 10 years apart (same time, same tz) → midpoint is exactly 5 years in.

        1990-01-01 12:00 UTC and 2000-01-01 12:00 UTC.
        The midpoint timestamp falls on 1994-12-31 or 1995-01-01 depending on leap years.
        We verify the exact date rather than just the year prefix.
        """
        profiles = [
            make_profile("1990-01-01", "12:00"),
            make_profile("2000-01-01", "12:00"),
        ]
        locations = [make_location(0.0, 0.0, "UTC")] * 2
        result = calculate_davison_midpoint(profiles, locations)
        # Exact midpoint: average of 1990-01-01 and 2000-01-01 timestamps
        # Due to leap years in 1992, 1996, the midpoint is 1994-12-31
        from datetime import datetime, timezone
        ts_a = datetime(1990, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp()
        ts_b = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp()
        expected_dt = datetime.fromtimestamp((ts_a + ts_b) / 2, tz=timezone.utc)
        expected_date = expected_dt.strftime("%Y-%m-%d")
        expected_time = expected_dt.strftime("%H:%M")
        assert result["date"] == expected_date
        assert result["time"] == expected_time

    def test_location_midpoint(self):
        """Location should be averaged."""
        profiles = [make_profile("2000-01-01", "12:00")] * 2
        locations = [make_location(0.0, -100.0, "UTC"), make_location(60.0, -80.0, "UTC")]
        result = calculate_davison_midpoint(profiles, locations)
        assert abs(result["latitude"] - 30.0) < 0.001
        assert abs(result["longitude"] - (-90.0)) < 0.001

    def test_three_profiles(self):
        """Three profiles — should average all three datetimes."""
        profiles = [
            make_profile("2000-01-01", "00:00"),
            make_profile("2000-01-01", "12:00"),
            make_profile("2000-01-02", "00:00"),
        ]
        locations = [make_location(0.0, 0.0, "UTC")] * 3
        result = calculate_davison_midpoint(profiles, locations)
        assert result["date"] == "2000-01-01"
        assert result["time"] == "12:00"

    def test_timezone_is_utc(self):
        """Davison midpoint is always expressed in UTC."""
        profiles = [make_profile("2000-06-15", "12:00")] * 2
        locations = [make_location(40.0, -74.0, "America/New_York")] * 2
        result = calculate_davison_midpoint(profiles, locations)
        assert result["timezone"] == "UTC"

    def test_result_has_all_keys(self):
        """Result should have date, time, latitude, longitude, timezone."""
        profiles = [make_profile("2000-01-01", "12:00")] * 2
        locations = [make_location(40.0, -74.0, "America/New_York")] * 2
        result = calculate_davison_midpoint(profiles, locations)
        assert all(k in result for k in ["date", "time", "latitude", "longitude", "timezone"])

    def test_date_format(self):
        """Date should be YYYY-MM-DD format."""
        profiles = [make_profile("1985-06-15", "08:30")] * 2
        locations = [make_location(38.6, -90.2, "America/Chicago")] * 2
        result = calculate_davison_midpoint(profiles, locations)
        parts = result["date"].split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2
        assert len(parts[2]) == 2

    def test_time_format(self):
        """Time should be HH:MM format."""
        profiles = [make_profile("2000-01-01", "08:30")] * 2
        locations = [make_location(0.0, 0.0, "UTC")] * 2
        result = calculate_davison_midpoint(profiles, locations)
        parts = result["time"].split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 2
        assert len(parts[1]) == 2

    def test_single_profile_raises(self):
        """Fewer than 2 profiles should raise ValueError."""
        with pytest.raises(ValueError, match="2"):
            calculate_davison_midpoint(
                [make_profile("2000-01-01", "12:00")],
                [make_location(0.0, 0.0, "UTC")]
            )

    def test_mismatched_lengths_raises(self):
        """Profiles and locations lists of different lengths should raise."""
        with pytest.raises(ValueError, match="same length"):
            calculate_davison_midpoint(
                [make_profile("2000-01-01", "12:00")] * 2,
                [make_location(0.0, 0.0, "UTC")]
            )

    def test_identical_profiles_same_timezone(self):
        """Two identical profiles in the same timezone → midpoint equals input."""
        profiles = [make_profile("1985-05-06", "00:50")] * 2
        locations = [make_location(38.627, -90.198, "America/Chicago")] * 2
        result = calculate_davison_midpoint(profiles, locations)
        # Midpoint of identical moments is that same moment — expressed in UTC
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        dt_local = datetime(1985, 5, 6, 0, 50, tzinfo=ZoneInfo("America/Chicago"))
        dt_utc = dt_local.astimezone(timezone.utc)
        assert result["date"] == dt_utc.strftime("%Y-%m-%d")
        assert result["time"] == dt_utc.strftime("%H:%M")
        assert abs(result["latitude"] - 38.627) < 0.001
        assert abs(result["longitude"] - (-90.198)) < 0.001


# =============================================================================
# enrich_natal_chart_for_composite
# =============================================================================

class TestEnrichNatalChartForComposite:
    """Tests for enrich_natal_chart_for_composite()."""

    def test_adds_missing_absolute_position_planet(self):
        """Should add absolute_position to planets that are missing it."""
        chart = {
            "planets": {"Sun": {"sign": "Taurus", "degree": 15.0}},
            "houses": {},
            "points": {},
        }
        enriched = enrich_natal_chart_for_composite(chart)
        # Taurus starts at 30°, so 15° Taurus = 45°
        assert abs(enriched["planets"]["Sun"]["absolute_position"] - 45.0) < 0.001

    def test_adds_missing_absolute_position_house(self):
        """Should add absolute_position to houses that are missing it."""
        chart = {
            "planets": {},
            "houses": {"1": {"sign": "Aries", "degree": 5.0}},
            "points": {},
        }
        enriched = enrich_natal_chart_for_composite(chart)
        assert abs(enriched["houses"]["1"]["absolute_position"] - 5.0) < 0.001

    def test_does_not_overwrite_existing(self):
        """Should not overwrite existing absolute_position values."""
        chart = {
            "planets": {"Sun": {"sign": "Taurus", "degree": 15.0, "absolute_position": 99.0}},
            "houses": {},
            "points": {},
        }
        enriched = enrich_natal_chart_for_composite(chart)
        assert enriched["planets"]["Sun"]["absolute_position"] == 99.0

    def test_all_12_signs_offsets(self):
        """Each sign should produce the correct absolute position offset."""
        sign_offsets = {
            "Aries": 0, "Taurus": 30, "Gemini": 60, "Cancer": 90,
            "Leo": 120, "Virgo": 150, "Libra": 180, "Scorpio": 210,
            "Sagittarius": 240, "Capricorn": 270, "Aquarius": 300, "Pisces": 330,
        }
        for sign, offset in sign_offsets.items():
            chart = {
                "planets": {"Sun": {"sign": sign, "degree": 0.0}},
                "houses": {},
                "points": {},
            }
            enriched = enrich_natal_chart_for_composite(chart)
            assert abs(enriched["planets"]["Sun"]["absolute_position"] - offset) < 0.001, \
                f"{sign}: expected {offset}, got {enriched['planets']['Sun']['absolute_position']}"

    def test_empty_chart(self):
        """Should handle empty chart without error."""
        chart = {"planets": {}, "houses": {}, "points": {}}
        enriched = enrich_natal_chart_for_composite(chart)
        assert enriched["planets"] == {}
        assert enriched["houses"] == {}
        assert enriched["points"] == {}

    def test_points_enriched(self):
        """Should add absolute_position to points as well."""
        chart = {
            "planets": {},
            "houses": {},
            "points": {"ASC": {"sign": "Capricorn", "degree": 5.0}},
        }
        enriched = enrich_natal_chart_for_composite(chart)
        assert abs(enriched["points"]["ASC"]["absolute_position"] - 275.0) < 0.001
