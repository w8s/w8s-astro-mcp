"""Ephemeris engine using pysweph (Swiss Ephemeris Python bindings).

Replaces the old swetest subprocess approach. Produces the same output dict
structure as the old parse_swetest_output() parser, so all downstream consumers
(transit_logger, connection_management, db_helpers) require no changes.

New fields added vs old swetest output:
    - planets[name]["is_retrograde"]     bool, derived from speed sign
    - planets[name]["absolute_position"] float, ecliptic longitude 0-360°
    - houses[n]["absolute_position"]     float, ecliptic longitude 0-360°
    - points[name]["absolute_position"]  float, ecliptic longitude 0-360°
    - metadata["ephemeris"]              str, "moshier" or "sweph"

Precision:
    - Moshier (default, no files needed): ~1 arcminute
    - Swiss Ephemeris files (.se1):       ~0.001 arcsecond
"""

from __future__ import annotations

import swisseph as swe
from datetime import datetime
from typing import Any, Optional

from ..constants import ZODIAC_SIGNS, PLANET_IDS, PLANET_NAMES, HOUSE_SYSTEM_CODES


class EphemerisError(Exception):
    """Raised when an ephemeris calculation fails."""
    pass


class EphemerisEngine:
    """Calculates planetary positions and house cusps using pysweph.

    Usage:
        engine = EphemerisEngine()                        # Moshier (no files needed)
        engine = EphemerisEngine(ephe_path="/path/ephe")  # Swiss Ephemeris files

        chart = engine.get_chart(latitude, longitude, date_str, time_str)
    """

    def __init__(self, ephe_path: Optional[str] = None):
        """Initialize the engine and configure the ephemeris source.

        Args:
            ephe_path: Path to directory containing .se1 ephemeris files.
                       Pass None (default) to use the built-in Moshier ephemeris,
                       which requires no external files.
        """
        self.ephe_path = ephe_path
        if ephe_path is not None:
            swe.set_ephe_path(ephe_path)
        else:
            # Explicitly activate Moshier so behavior is predictable
            # even if the caller later changes the global path.
            swe.set_ephe_path(None)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_chart(
        self,
        latitude: float,
        longitude: float,
        date_str: Optional[str] = None,
        time_str: str = "12:00",
        house_system_code: str = "P",
    ) -> dict[str, Any]:
        """Calculate a full chart for a given location and date/time.

        Args:
            latitude: Geographic latitude in decimal degrees.
            longitude: Geographic longitude in decimal degrees.
            date_str: Date in YYYY-MM-DD format. Defaults to today.
            time_str: Time in HH:MM format (UT). Defaults to "12:00".
            house_system_code: Single-letter house system code or full name.
                               Defaults to "P" (Placidus).

        Returns:
            Dict with keys: "planets", "houses", "points", "metadata".
            Structure is backward-compatible with parse_swetest_output().

        Raises:
            EphemerisError: If date/time cannot be parsed or calculation fails.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise EphemerisError(
                f"Invalid date format: {date_str!r}. Expected YYYY-MM-DD."
            )

        hour = self._parse_time(time_str)
        jd = self._to_jd(dt.year, dt.month, dt.day, hour)
        hsys = self._house_system_bytes(house_system_code)
        house_system_name = self._house_system_name(house_system_code)

        planets = self._calc_planets(jd)
        houses, points = self._calc_houses(jd, latitude, longitude, hsys)

        return {
            "planets": planets,
            "houses": houses,
            "points": points,
            "metadata": {
                "date": date_str,
                "time": f"{time_str}:00" if time_str else "12:00:00",
                "latitude": latitude,
                "longitude": longitude,
                "house_system": house_system_name,
                "ephemeris": self.get_mode(),
            },
        }

    # Backward-compatible alias used by server.py and callers that still
    # reference the old SweetestIntegration.get_transits() name.
    def get_transits(
        self,
        latitude: float,
        longitude: float,
        date_str: Optional[str] = None,
        time_str: str = "12:00",
        house_system_code: str = "P",
    ) -> dict[str, Any]:
        """Alias for get_chart(). Provided for backward compatibility."""
        return self.get_chart(latitude, longitude, date_str, time_str, house_system_code)

    def get_mode(self) -> str:
        """Return the active ephemeris mode: 'moshier' or 'sweph'."""
        return "moshier" if self.ephe_path is None else "sweph"

    # ------------------------------------------------------------------
    # Internal calculations
    # ------------------------------------------------------------------

    def _calc_planets(self, jd: float) -> dict[str, Any]:
        """Calculate positions for the ten main planets."""
        result = {}
        for planet_id, planet_name in zip(PLANET_IDS, PLANET_NAMES):
            try:
                # pysweph fork returns (xx, ret_flags, warning_str) — unpack flexibly
                raw = swe.calc_ut(jd, planet_id)
                xx = raw[0]  # 6-element tuple: lon, lat, dist, speed_lon, speed_lat, speed_dist
            except Exception as exc:
                raise EphemerisError(f"Failed to calculate {planet_name}: {exc}") from exc

            longitude = xx[0]
            speed = xx[3]

            info = self._longitude_to_sign_info(longitude)
            info["is_retrograde"] = self._is_retrograde(speed)
            result[planet_name] = info

        return result

    def _calc_houses(
        self, jd: float, lat: float, lng: float, hsys: bytes
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Calculate house cusps and the Ascendant/MC angles."""
        try:
            cusps, ascmc = swe.houses(jd, lat, lng, hsys)
        except Exception as exc:
            raise EphemerisError(f"Failed to calculate houses: {exc}") from exc

        # cusps is a 13-element tuple; index 0 is unused, 1-12 are the cusps.
        houses: dict[str, Any] = {}
        for i in range(1, 13):
            houses[str(i)] = self._longitude_to_sign_info(cusps[i])

        # ascmc[0] = Ascendant, ascmc[1] = MC
        points: dict[str, Any] = {
            "Ascendant": self._longitude_to_sign_info(ascmc[0]),
            "MC": self._longitude_to_sign_info(ascmc[1]),
        }

        return houses, points

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _to_jd(self, year: int, month: int, day: int, hour: float) -> float:
        """Convert a calendar date and decimal hour (UT) to Julian Day number."""
        return swe.julday(year, month, day, hour)

    def _parse_time(self, time_str: str) -> float:
        """Convert 'HH:MM' to decimal hours.

        Raises:
            EphemerisError: If the time string is not valid HH:MM.
        """
        try:
            parts = time_str.split(":")
            if len(parts) < 2:
                raise ValueError("not enough parts")
            h = int(parts[0])
            m = int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError(f"out of range: {h}:{m}")
            return h + m / 60.0
        except (ValueError, AttributeError) as exc:
            raise EphemerisError(
                f"Invalid time format: {time_str!r}. Expected HH:MM."
            ) from exc

    def _longitude_to_sign_info(self, longitude: float) -> dict[str, Any]:
        """Convert an absolute ecliptic longitude (0-360°) to sign metadata.

        Returns a dict with:
            sign              str   — e.g. "Aquarius"
            degree            float — degrees within the sign (0–<30)
            formatted         str   — e.g. "14°39'"
            absolute_position float — original longitude value
        """
        # Normalise to [0, 360)
        longitude = longitude % 360.0

        sign_index = int(longitude // 30)
        degree_in_sign = longitude % 30.0

        deg = int(degree_in_sign)
        minutes_float = (degree_in_sign - deg) * 60.0
        minutes = int(minutes_float)

        return {
            "sign": ZODIAC_SIGNS[sign_index],
            "degree": degree_in_sign,
            "formatted": f"{deg}°{minutes:02d}'",
            "absolute_position": longitude,
        }

    def _is_retrograde(self, speed: float) -> bool:
        """Return True if the planet is retrograde (speed < 0)."""
        return speed < 0

    def _house_system_bytes(self, code: str) -> bytes:
        """Return the single-byte house system code expected by swe.houses().

        Accepts either the single-letter code ('P') or the full name ('Placidus').
        Falls back to b"P" (Placidus) for unknown values.
        """
        # Normalize full names to codes
        normalized = HOUSE_SYSTEM_CODES.get(code.strip(), code.strip())
        if len(normalized) == 1 and normalized.upper() in "PKORCAESVXHBYDGFW":
            return normalized.upper().encode()
        # Unknown — fall back to Placidus
        return b"P"

    def _house_system_name(self, code: str) -> str:
        """Return the display name for a house system code."""
        names = {
            "P": "Placidus", "K": "Koch", "O": "Porphyrius",
            "R": "Regiomontanus", "C": "Campanus", "A": "Equal",
            "E": "Equal", "V": "Vehlow Equal", "X": "Axial Rotation",
            "H": "Azimuthal", "B": "Alcabitus", "Y": "APC Houses",
            "D": "Morinus", "G": "Gauquelin Sectors", "F": "Carter",
            "W": "Whole Sign",
        }
        # Allow full-name lookup via HOUSE_SYSTEM_CODES first
        single = HOUSE_SYSTEM_CODES.get(code.strip(), code.strip())
        return names.get(single.upper(), f"House System {code}")
