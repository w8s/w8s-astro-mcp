"""Shared constants for w8s-astro-mcp.

Centralizes values used by the ephemeris engine and potentially other modules,
so they are defined once and imported wherever needed.
"""

import swisseph as swe

# Zodiac signs in ecliptic order (index 0 = Aries, index 11 = Pisces).
# Used to convert an absolute longitude to a sign name: sign = ZODIAC_SIGNS[int(lon // 30)]
ZODIAC_SIGNS: list[str] = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Ten main planets in the order we calculate them.
# Each entry is a (pysweph_constant, display_name) pair so the two lists stay in sync.
_PLANET_PAIRS: list[tuple[int, str]] = [
    (swe.SUN,     "Sun"),
    (swe.MOON,    "Moon"),
    (swe.MERCURY, "Mercury"),
    (swe.VENUS,   "Venus"),
    (swe.MARS,    "Mars"),
    (swe.JUPITER, "Jupiter"),
    (swe.SATURN,  "Saturn"),
    (swe.URANUS,  "Uranus"),
    (swe.NEPTUNE, "Neptune"),
    (swe.PLUTO,   "Pluto"),
]

PLANET_IDS:   list[int] = [p[0] for p in _PLANET_PAIRS]
PLANET_NAMES: list[str] = [p[1] for p in _PLANET_PAIRS]

# Maps full house system names to single-letter codes used by swe.houses().
# Single-letter codes pass through unchanged (looked up as their own key).
HOUSE_SYSTEM_CODES: dict[str, str] = {
    "Placidus":          "P",
    "Koch":              "K",
    "Porphyrius":        "O",
    "Regiomontanus":     "R",
    "Campanus":          "C",
    "Equal":             "E",
    "Vehlow Equal":      "V",
    "Whole Sign":        "W",
    "Axial Rotation":    "X",
    "Azimuthal":         "H",
    "Alcabitus":         "B",
    "APC Houses":        "Y",
    "Morinus":           "D",
    "Gauquelin Sectors": "G",
    "Carter":            "F",
}
