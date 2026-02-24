"""
Tests for geocoding.py — get_timezone_for_coords and geocode_location.

get_timezone_for_coords uses timezonefinder (offline, deterministic) — tested directly.
geocode_location hits Nominatim over the network — mocked to avoid flakiness in CI.
"""

import pytest
from unittest.mock import patch, MagicMock
from w8s_astro_mcp.utils.geocoding import get_timezone_for_coords, geocode_location


# ---------------------------------------------------------------------------
# get_timezone_for_coords — offline, deterministic, no mocking needed
# ---------------------------------------------------------------------------

class TestGetTimezoneForCoords:
    def test_bangkok(self):
        tz = get_timezone_for_coords(lat=13.7563, lon=100.5018)
        assert tz == "Asia/Bangkok"

    def test_seattle(self):
        tz = get_timezone_for_coords(lat=47.6062, lon=-122.3321)
        assert tz == "America/Los_Angeles"

    def test_chicago(self):
        tz = get_timezone_for_coords(lat=41.8781, lon=-87.6298)
        assert tz == "America/Chicago"

    def test_london(self):
        tz = get_timezone_for_coords(lat=51.5074, lon=-0.1278)
        assert tz == "Europe/London"

    def test_paris(self):
        tz = get_timezone_for_coords(lat=48.8566, lon=2.3522)
        assert tz == "Europe/Paris"

    def test_open_ocean_returns_a_timezone(self):
        # timezonefinder has ocean timezone polygons — returns Etc/GMT+N, not UTC
        tz = get_timezone_for_coords(lat=0.0, lon=-170.0)
        assert tz is not None
        assert len(tz) > 0


# ---------------------------------------------------------------------------
# geocode_location — mocked network call
# ---------------------------------------------------------------------------

NOMINATIM_BANGKOK = [{
    "lat": "13.7563",
    "lon": "100.5018",
    "display_name": "Bangkok, Thailand",
}]

NOMINATIM_SEATTLE = [{
    "lat": "47.6062",
    "lon": "-122.3321",
    "display_name": "Seattle, King County, Washington, United States",
}]


class TestGeocodeLocation:
    def _mock_nominatim(self, payload):
        """Return a context manager mock that yields encoded JSON."""
        import json
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(
            read=MagicMock(return_value=json.dumps(payload).encode())
        ))
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    def test_bangkok_returns_correct_timezone(self):
        with patch("urllib.request.urlopen", return_value=self._mock_nominatim(NOMINATIM_BANGKOK)):
            result = geocode_location("Bangkok, Thailand")
        assert result is not None
        assert abs(result["latitude"] - 13.7563) < 0.01
        assert result["timezone"] == "Asia/Bangkok"

    def test_seattle_returns_correct_timezone(self):
        with patch("urllib.request.urlopen", return_value=self._mock_nominatim(NOMINATIM_SEATTLE)):
            result = geocode_location("Seattle, WA")
        assert result is not None
        assert result["timezone"] == "America/Los_Angeles"

    def test_not_found_returns_none(self):
        with patch("urllib.request.urlopen", return_value=self._mock_nominatim([])):
            result = geocode_location("NotARealPlaceXYZ")
        assert result is None

    def test_network_error_returns_none(self):
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            result = geocode_location("Bangkok")
        assert result is None

    def test_result_includes_required_keys(self):
        with patch("urllib.request.urlopen", return_value=self._mock_nominatim(NOMINATIM_BANGKOK)):
            result = geocode_location("Bangkok")
        assert result is not None
        for key in ("name", "latitude", "longitude", "timezone"):
            assert key in result
