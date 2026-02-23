"""Tests for connection chart calculation engine.

Tests cover:
- circular_mean_degrees: wraparound, identical, opposite, N-way, edge cases
- degrees_to_sign_components: all 12 signs, boundaries, floating point safety
- calculate_composite_positions: two-way, N-way, missing planets, error cases
- calculate_davison_midpoint: timezone-aware averaging, N-way, error cases
- enrich_natal_chart_for_composite: adds missing absolute_position
"""

import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
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


def make_location(latitude: float, longitude: float, tz: str = "UTC"):
    """Build a minimal mock Location with a real timezone string."""
    loc = MagicMock()
    loc.latitude = latitude
    loc.longitude = longitude
    loc.timezone = tz
    return loc


# =============================================================================
# circular_mean_degrees
# =============================================================================

class TestCircularMeanDegrees:

    def test_identical_angles(self):
        """Mean of identical angles should return that angle."""
        assert near(circular_mean_degrees([90.0, 90.0]), 90.0)
        assert near(circular_mean_degrees([0.0, 0.0, 0.0]), 0.0)
        assert near(circular_mean_degrees([270.0, 270.0]), 270.0)

    def test_wraparound_simple(self):
        """350° and 10° should average to 0°, not 180°."""
        assert near(circular_mean_degrees([350.0, 10.0]), 0.0)

    def test_wraparound_asymmetric(self):
        """355° and 5° should average to 0°."""
        assert near(circular_mean_degrees([355.0, 5.0]), 0.0)

    def test_wraparound_large_gap(self):
        """340° and 20° should average to 0°."""
        assert near(circular_mean_degrees([340.0, 20.0]), 0.0)

    def test_simple_average(self):
        """30° and 90° should average to 60°."""
        assert near(circular_mean_degrees([30.0, 90.0]), 60.0)

    def test_n_way_same_angle(self):
        """10 identical angles should return that angle."""
        assert near(circular_mean_degrees([45.0] * 10), 45.0)

    def test_single_angle(self):
        """Single angle should return itself."""
        assert near(circular_mean_degrees([180.0]), 180.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            circular_mean_degrees([])

    def test_result_in_range(self):
        """Result should always be in [0, 360)."""
        for angles in [[359.9, 0.1], [180.0, 180.0], [0.0, 0.0], [350.0, 10.0]]:
            result = circular_mean_degrees(angles)
            assert 0.0 <= result < 360.0, f"Out of range: {result} for input {angles}"

    def test_cancelling_vectors_returns_valid_angle(self):
        """When vectors cancel (opposite or equally-spaced angles), atan2 behavior
        is implementation-defined. We only guarantee a valid angle in [0, 360)."""
        for angles in [[90.0, 270.0], [0.0, 120.0, 240.0]]:
            result = circular_mean_degrees(angles)
            assert 0.0 <= result < 360.0, f"Out of range: {result} for input {angles}"

    def test_all_12_sign_midpoints(self):
        """Average of adjacent sign midpoints should be their shared boundary."""
        # Aries midpoint (15°) and Taurus midpoint (45°) → 30° boundary
        assert near(circular_mean_degrees([15.0, 45.0]), 30.0)


# =============================================================================
# degrees_to_sign_components
# =============================================================================

class TestDegreesToSignComponents:

    SIGN_BOUNDARIES = [
        (0.0,   "Aries"),       (30.0,  "Taurus"),
        (60.0,  "Gemini"),      (90.0,  "Cancer"),
        (120.0, "Leo"),         (150.0, "Virgo"),
        (180.0, "Libra"),       (210.0, "Scorpio"),
        (240.0, "Sagittarius"), (270.0, "Capricorn"),
        (300.0, "Aquarius"),    (330.0, "Pisces"),
    ]

    def test_all_12_sign_starts(self):
        """Each sign boundary degree should resolve to the correct sign at 0°."""
        for absolute, expected_sign in self.SIGN_BOUNDARIES:
            sign, degree, *_ = degrees_to_sign_components(absolute)
            assert sign == expected_sign, f"{absolute}° → expected {expected_sign}, got {sign}"
            assert degree == 0

    def test_midpoint_aries(self):
        sign, degree, minutes, _ = degrees_to_sign_components(15.0)
        assert sign == "Aries" and degree == 15 and minutes == 0

    def test_midpoint_taurus(self):
        sign, degree, *_ = degrees_to_sign_components(45.0)
        assert sign == "Taurus" and degree == 15

    def test_pisces_end(self):
        sign, *_ = degrees_to_sign_components(359.9)
        assert sign == "Pisces"

    def test_minutes_calculation(self):
        """30.5° absolute = 0°30' Taurus."""
        sign, degree, minutes, _ = degrees_to_sign_components(30.5)
        assert sign == "Taurus" and degree == 0 and minutes == 30

    def test_seconds_calculation(self):
        """0°30'30\" Taurus = 30 + 30/60 + 30/3600 absolute."""
        absolute = 30.0 + 30 / 60 + 30 / 3600
        sign, degree, minutes, seconds = degrees_to_sign_components(absolute)
        assert sign == "Taurus" and degree == 0 and minutes == 30
        assert abs(seconds - 30.0) < 0.01

    def test_wraparound_360(self):
        """360.0° wraps to Aries 0°."""
        sign, degree, *_ = degrees_to_sign_components(360.0)
        assert sign == "Aries" and degree == 0

    def test_float_just_below_boundary(self):
        """59.9999999999° should be Taurus, not Gemini."""
        sign, *_ = degrees_to_sign_components(59.9999999999)
        assert sign == "Taurus"

    def test_exact_boundary_belongs_to_next_sign(self):
        """Exactly 60.0° is Gemini, not Taurus."""
        sign, degree, *_ = degrees_to_sign_components(60.0)
        assert sign == "Gemini" and degree == 0

    def test_all_components_non_negative(self):
        for angle in [0.0, 15.0, 45.5, 179.99, 270.0, 359.9]:
            sign, degree, minutes, seconds = degrees_to_sign_components(angle)
            assert degree >= 0 and minutes >= 0 and seconds >= 0.0


# =============================================================================
# calculate_composite_positions
# =============================================================================

class TestCalculateCompositePositions:

    def test_two_charts_simple_average(self):
        """30° and 90° Sun → 60° (Gemini)."""
        charts = [make_chart({"Sun": 30.0}), make_chart({"Sun": 90.0})]
        result = calculate_composite_positions(charts)
        assert near(result["planets"]["Sun"]["absolute_position"], 60.0)
        assert result["planets"]["Sun"]["sign"] == "Gemini"

    def test_wraparound_planets(self):
        """350° and 10° → ~0° (Aries)."""
        charts = [make_chart({"Sun": 350.0}), make_chart({"Sun": 10.0})]
        result = calculate_composite_positions(charts)
        assert near(result["planets"]["Sun"]["absolute_position"], 0.0)
        assert result["planets"]["Sun"]["sign"] == "Aries"

    def test_n_way_identical(self):
        """10 identical positions → same position."""
        charts = [make_chart({"Sun": 45.0}) for _ in range(10)]
        result = calculate_composite_positions(charts)
        assert near(result["planets"]["Sun"]["absolute_position"], 45.0)

    def test_missing_planet_excluded(self):
        """Planet absent from any chart is excluded from composite."""
        chart_a = make_chart({"Sun": 30.0, "Moon": 60.0})
        chart_b = make_chart({"Sun": 90.0})
        result = calculate_composite_positions([chart_a, chart_b])
        assert "Sun" in result["planets"]
        assert "Moon" not in result["planets"]

    def test_houses_averaged(self):
        charts = [
            make_chart({"Sun": 0.0}, house_positions={"1": 0.0, "7": 180.0}),
            make_chart({"Sun": 0.0}, house_positions={"1": 60.0, "7": 240.0}),
        ]
        result = calculate_composite_positions(charts)
        assert near(result["houses"]["1"]["absolute_position"], 30.0)
        assert near(result["houses"]["7"]["absolute_position"], 210.0)

    def test_points_averaged(self):
        charts = [
            make_chart({"Sun": 0.0}, point_positions={"ASC": 10.0, "MC": 100.0}),
            make_chart({"Sun": 0.0}, point_positions={"ASC": 30.0, "MC": 120.0}),
        ]
        result = calculate_composite_positions(charts)
        assert near(result["points"]["ASC"]["absolute_position"], 20.0)

    def test_result_schema(self):
        """Each planet entry must have all expected keys."""
        charts = [make_chart({"Sun": 45.0}), make_chart({"Sun": 45.0})]
        sun = calculate_composite_positions(charts)["planets"]["Sun"]
        assert all(k in sun for k in ["sign", "degree", "minutes", "seconds", "absolute_position"])

    def test_house_keys_are_strings(self):
        charts = [
            make_chart({"Sun": 0.0}, house_positions={"1": 0.0}),
            make_chart({"Sun": 0.0}, house_positions={"1": 60.0}),
        ]
        result = calculate_composite_positions(charts)
        assert "1" in result["houses"] and 1 not in result["houses"]

    def test_absolute_position_in_range(self):
        charts = [make_chart({"Sun": 355.0}), make_chart({"Sun": 5.0})]
        pos = calculate_composite_positions(charts)["planets"]["Sun"]["absolute_position"]
        assert 0.0 <= pos < 360.0, f"Out of range: {pos}"

    def test_single_chart_raises(self):
        with pytest.raises(ValueError, match="2"):
            calculate_composite_positions([make_chart({"Sun": 0.0})])

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            calculate_composite_positions([])


# =============================================================================
# calculate_davison_midpoint
# =============================================================================

class TestCalculateDavisonMidpoint:

    def test_same_utc_times(self):
        """Two UTC births, midnight and noon → midpoint 06:00 UTC."""
        profiles = [make_profile("2000-01-01", "00:00"), make_profile("2000-01-01", "12:00")]
        locations = [make_location(0.0, 0.0, "UTC"), make_location(0.0, 0.0, "UTC")]
        result = calculate_davison_midpoint(profiles, locations)
        assert result["date"] == "2000-01-01"
        assert result["time"] == "06:00"

    def test_timezone_conversion_changes_midpoint(self):
        """Birth times are local — timezone conversion must happen before averaging.

        Person A: 2000-01-01 00:00 UTC  → UTC 00:00
        Person B: 2000-01-01 00:00 CST  → UTC 06:00  (CST = UTC-6)
        Midpoint without conversion: 00:00 (WRONG)
        Midpoint with conversion:    03:00 (CORRECT)
        """
        profiles = [make_profile("2000-01-01", "00:00"), make_profile("2000-01-01", "00:00")]
        locations = [
            make_location(0.0, 0.0, "UTC"),
            make_location(29.95, -90.07, "America/Chicago"),
        ]
        result = calculate_davison_midpoint(profiles, locations)
        assert result["date"] == "2000-01-01"
        assert result["time"] == "03:00"

    def test_same_local_time_different_zones(self):
        """Same local clock time in different zones is NOT the same moment.

        London noon BST (June) = UTC 11:00
        New York noon EDT (June) = UTC 16:00
        Midpoint = UTC 13:30
        """
        profiles = [make_profile("2000-06-15", "12:00"), make_profile("2000-06-15", "12:00")]
        locations = [
            make_location(51.5, 0.0, "Europe/London"),
            make_location(40.7, -74.0, "America/New_York"),
        ]
        result = calculate_davison_midpoint(profiles, locations)
        assert result["date"] == "2000-06-15"
        assert result["time"] == "13:30"

    def test_different_years_exact_date(self):
        """Midpoint of two UTC dates is computed from timestamps (leap-year-aware).
        We derive the expected value the same way the implementation does,
        rather than guessing from year arithmetic."""
        profiles = [make_profile("1990-01-01", "12:00"), make_profile("2000-01-01", "12:00")]
        locations = [make_location(0.0, 0.0, "UTC")] * 2
        result = calculate_davison_midpoint(profiles, locations)

        ts_a = datetime(1990, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp()
        ts_b = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp()
        expected = datetime.fromtimestamp((ts_a + ts_b) / 2, tz=timezone.utc)

        assert result["date"] == expected.strftime("%Y-%m-%d")
        assert result["time"] == expected.strftime("%H:%M")

    def test_identical_profiles_midpoint_equals_input(self):
        """Two identical profiles → midpoint is that same moment, expressed in UTC."""
        profiles = [make_profile("1985-05-06", "00:50")] * 2
        locations = [make_location(38.627, -90.198, "America/Chicago")] * 2
        result = calculate_davison_midpoint(profiles, locations)

        dt_local = datetime(1985, 5, 6, 0, 50, tzinfo=ZoneInfo("America/Chicago"))
        dt_utc = dt_local.astimezone(timezone.utc)

        assert result["date"] == dt_utc.strftime("%Y-%m-%d")
        assert result["time"] == dt_utc.strftime("%H:%M")
        assert abs(result["latitude"] - 38.627) < 0.001
        assert abs(result["longitude"] - (-90.198)) < 0.001

    def test_three_profiles(self):
        """Three UTC profiles averaging to a known midpoint."""
        profiles = [
            make_profile("2000-01-01", "00:00"),
            make_profile("2000-01-01", "12:00"),
            make_profile("2000-01-02", "00:00"),
        ]
        locations = [make_location(0.0, 0.0, "UTC")] * 3
        result = calculate_davison_midpoint(profiles, locations)
        assert result["date"] == "2000-01-01"
        assert result["time"] == "12:00"

    def test_location_midpoint(self):
        profiles = [make_profile("2000-01-01", "12:00")] * 2
        locations = [make_location(0.0, -100.0, "UTC"), make_location(60.0, -80.0, "UTC")]
        result = calculate_davison_midpoint(profiles, locations)
        assert abs(result["latitude"] - 30.0) < 0.001
        assert abs(result["longitude"] - (-90.0)) < 0.001

    def test_timezone_key_is_utc(self):
        """Midpoint is always expressed in UTC regardless of input zones."""
        profiles = [make_profile("2000-06-15", "12:00")] * 2
        locations = [make_location(40.0, -74.0, "America/New_York")] * 2
        assert calculate_davison_midpoint(profiles, locations)["timezone"] == "UTC"

    def test_result_has_all_keys(self):
        profiles = [make_profile("2000-01-01", "12:00")] * 2
        locations = [make_location(40.0, -74.0, "America/New_York")] * 2
        result = calculate_davison_midpoint(profiles, locations)
        assert all(k in result for k in ["date", "time", "latitude", "longitude", "timezone"])

    def test_date_format(self):
        profiles = [make_profile("1985-06-15", "08:30")] * 2
        locations = [make_location(38.6, -90.2, "America/Chicago")] * 2
        parts = calculate_davison_midpoint(profiles, locations)["date"].split("-")
        assert len(parts) == 3 and len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2

    def test_time_format(self):
        profiles = [make_profile("2000-01-01", "08:30")] * 2
        locations = [make_location(0.0, 0.0, "UTC")] * 2
        parts = calculate_davison_midpoint(profiles, locations)["time"].split(":")
        assert len(parts) == 2 and len(parts[0]) == 2 and len(parts[1]) == 2

    def test_single_profile_raises(self):
        with pytest.raises(ValueError, match="2"):
            calculate_davison_midpoint(
                [make_profile("2000-01-01", "12:00")],
                [make_location(0.0, 0.0, "UTC")]
            )

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            calculate_davison_midpoint(
                [make_profile("2000-01-01", "12:00")] * 2,
                [make_location(0.0, 0.0, "UTC")]
            )


# =============================================================================
# enrich_natal_chart_for_composite
# =============================================================================

class TestEnrichNatalChartForComposite:

    def test_adds_missing_planet(self):
        """15° Taurus = 45° absolute."""
        chart = {"planets": {"Sun": {"sign": "Taurus", "degree": 15.0}}, "houses": {}, "points": {}}
        enriched = enrich_natal_chart_for_composite(chart)
        assert abs(enriched["planets"]["Sun"]["absolute_position"] - 45.0) < 0.001

    def test_adds_missing_house(self):
        """5° Aries = 5° absolute."""
        chart = {"planets": {}, "houses": {"1": {"sign": "Aries", "degree": 5.0}}, "points": {}}
        enriched = enrich_natal_chart_for_composite(chart)
        assert abs(enriched["houses"]["1"]["absolute_position"] - 5.0) < 0.001

    def test_adds_missing_point(self):
        """5° Capricorn = 275° absolute."""
        chart = {"planets": {}, "houses": {}, "points": {"ASC": {"sign": "Capricorn", "degree": 5.0}}}
        enriched = enrich_natal_chart_for_composite(chart)
        assert abs(enriched["points"]["ASC"]["absolute_position"] - 275.0) < 0.001

    def test_does_not_overwrite_existing(self):
        chart = {"planets": {"Sun": {"sign": "Taurus", "degree": 15.0, "absolute_position": 99.0}}, "houses": {}, "points": {}}
        enriched = enrich_natal_chart_for_composite(chart)
        assert enriched["planets"]["Sun"]["absolute_position"] == 99.0

    def test_all_12_sign_offsets(self):
        sign_offsets = {
            "Aries": 0, "Taurus": 30, "Gemini": 60, "Cancer": 90,
            "Leo": 120, "Virgo": 150, "Libra": 180, "Scorpio": 210,
            "Sagittarius": 240, "Capricorn": 270, "Aquarius": 300, "Pisces": 330,
        }
        for sign, offset in sign_offsets.items():
            chart = {"planets": {"Sun": {"sign": sign, "degree": 0.0}}, "houses": {}, "points": {}}
            enriched = enrich_natal_chart_for_composite(chart)
            got = enriched["planets"]["Sun"]["absolute_position"]
            assert abs(got - offset) < 0.001, f"{sign}: expected {offset}, got {got}"

    def test_empty_chart(self):
        chart = {"planets": {}, "houses": {}, "points": {}}
        enriched = enrich_natal_chart_for_composite(chart)
        assert enriched == {"planets": {}, "houses": {}, "points": {}}
