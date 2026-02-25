"""Electional astrology scoring utility (Phase 8).

Evaluates a chart dict against a set of electional criteria and returns
which criteria are met along with brief explanatory notes for failures.

Usage:
    from .electional import score_chart

    met, details = score_chart(chart, ["moon_not_void", "no_retrograde_inner"])
    # met: list of criterion names that passed
    # details: dict of criterion -> explanation string (for failures)
"""

from typing import Optional

# Signs in order (0-based index = sign number 0–11)
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

SIGN_INDEX = {s: i for i, s in enumerate(SIGNS)}

# Planets considered "inner" (fast-moving, most election-sensitive)
INNER_PLANETS = {"Mercury", "Venus"}

# Planets considered "outer" for retrograde checking
OUTER_PLANETS = {"Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}

# Benefic planets for angular house check
BENEFICS = {"Venus", "Jupiter"}

# Angular houses
ANGULAR_HOUSES = {1, 4, 7, 10}


def _absolute_position(sign: str, degree: float) -> float:
    """Convert sign + within-sign degree to 0–360° position."""
    idx = SIGN_INDEX.get(sign, 0)
    return idx * 30.0 + degree


def score_chart(chart: dict, criteria: list[str]) -> tuple[list[str], dict[str, str]]:
    """Evaluate a chart against electional criteria.

    Args:
        chart: Dict with 'planets', 'houses', 'points' keys as returned
               by EphemerisEngine.get_chart().
        criteria: List of criterion name strings to evaluate.

    Returns:
        Tuple of:
        - met: list of criterion names that passed
        - details: dict mapping criterion name -> explanation string
                   (populated for both passed and failed criteria)
    """
    planets = chart.get("planets", {})
    houses = chart.get("houses", {})
    points = chart.get("points", {})

    met = []
    details = {}

    for criterion in criteria:
        passed, note = _evaluate(criterion, planets, houses, points)
        details[criterion] = note
        if passed:
            met.append(criterion)

    return met, details


def _evaluate(
    criterion: str,
    planets: dict,
    houses: dict,
    points: dict,
) -> tuple[bool, str]:
    """Evaluate a single criterion. Returns (passed, explanation_note)."""

    if criterion == "moon_not_void":
        return _check_moon_not_void(planets)

    elif criterion == "no_retrograde_inner":
        return _check_no_retrograde(planets, INNER_PLANETS)

    elif criterion == "no_retrograde_outer":
        return _check_no_retrograde(planets, OUTER_PLANETS)

    elif criterion == "no_retrograde_all":
        return _check_no_retrograde(planets, INNER_PLANETS | OUTER_PLANETS)

    elif criterion == "moon_waxing":
        return _check_moon_phase(planets, waxing=True)

    elif criterion == "moon_waning":
        return _check_moon_phase(planets, waxing=False)

    elif criterion == "benefic_angular":
        return _check_benefic_angular(planets)

    elif criterion == "asc_not_late":
        return _check_asc_not_late(points)

    else:
        return False, f"Unknown criterion: {criterion}"


MAJOR_ASPECT_ANGLES = [0, 60, 90, 120, 180]
MAJOR_ASPECT_ORB = 8.0

# Planets to check for Moon aspects (exclude Moon itself)
ASPECT_PLANETS = {
    "Sun", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
}


def _check_moon_not_void(planets: dict) -> tuple[bool, str]:
    """Moon is not void of course.

    The Moon is void of course when it will make no more major aspects
    (conjunction, sextile, square, trine, opposition) to other planets
    before it leaves its current sign.

    Implementation: compute the Moon's absolute position and the absolute
    position of the sign boundary it is approaching (the next 30° cusp).
    For every other planet, check whether any major aspect angle falls
    between the Moon's current position and that boundary within the
    standard 8° orb. If at least one applying aspect exists, the Moon
    is not void.
    """
    moon = planets.get("Moon")
    if not moon:
        return True, "Moon data unavailable — assuming not void"

    moon_sign = moon.get("sign", "")
    moon_deg_in_sign = float(moon.get("degree", 0))
    moon_abs = _absolute_position(moon_sign, moon_deg_in_sign)

    # Absolute position of the upcoming sign boundary
    sign_idx = SIGN_INDEX.get(moon_sign, 0)
    boundary_abs = ((sign_idx + 1) % 12) * 30.0
    if boundary_abs == 0.0:
        boundary_abs = 360.0  # Pisces → Aries wraps

    remaining = (boundary_abs - moon_abs) % 360.0

    applying_aspects = []

    for planet_name in ASPECT_PLANETS:
        planet = planets.get(planet_name)
        if not planet:
            continue

        planet_abs = planet.get("absolute_position")
        if planet_abs is None:
            planet_abs = _absolute_position(
                planet.get("sign", "Aries"), float(planet.get("degree", 0))
            )

        for angle in MAJOR_ASPECT_ANGLES:
            for target in ((planet_abs + angle) % 360.0, (planet_abs - angle) % 360.0):
                travel = (target - moon_abs) % 360.0
                if travel == 0:
                    continue  # already exact — not applying
                if travel <= remaining + MAJOR_ASPECT_ORB:
                    orb_now = abs((moon_abs - target + 180) % 360 - 180)
                    if orb_now <= MAJOR_ASPECT_ORB:
                        names = {0: "conjunction", 60: "sextile", 90: "square",
                                 120: "trine", 180: "opposition"}
                        applying_aspects.append(
                            f"Moon {names[angle]} {planet_name} ({orb_now:.1f}° orb)"
                        )
            if applying_aspects:
                break

    if applying_aspects:
        return True, f"Moon not void — {applying_aspects[0]}"

    return False, (
        f"Moon void of course in {moon_sign} ({moon_deg_in_sign:.1f}°) — "
        f"no major aspects before sign change ({remaining:.1f}° remaining)"
    )


def _check_no_retrograde(planets: dict, planet_set: set) -> tuple[bool, str]:
    """All planets in planet_set are direct (not retrograde)."""
    retro = [
        name for name in planet_set
        if planets.get(name, {}).get("is_retrograde", False)
    ]
    if retro:
        return False, f"Retrograde: {', '.join(sorted(retro))}"
    return True, "All direct"


def _check_moon_phase(planets: dict, waxing: bool) -> tuple[bool, str]:
    """Moon phase check based on Sun/Moon relative position."""
    sun = planets.get("Sun")
    moon = planets.get("Moon")
    if not sun or not moon:
        return False, "Sun or Moon data unavailable"

    sun_abs = sun.get("absolute_position") or _absolute_position(
        sun.get("sign", "Aries"), sun.get("degree", 0)
    )
    moon_abs = moon.get("absolute_position") or _absolute_position(
        moon.get("sign", "Aries"), moon.get("degree", 0)
    )

    diff = (moon_abs - sun_abs) % 360
    is_waxing = diff < 180

    if waxing:
        if is_waxing:
            return True, f"Moon waxing ({diff:.1f}° from Sun)"
        return False, f"Moon waning ({diff:.1f}° from Sun)"
    else:
        if not is_waxing:
            return True, f"Moon waning ({diff:.1f}° from Sun)"
        return False, f"Moon waxing ({diff:.1f}° from Sun)"


def _check_benefic_angular(planets: dict) -> tuple[bool, str]:
    """Venus or Jupiter is in an angular house (1, 4, 7, 10)."""
    angular = []
    for name in BENEFICS:
        p = planets.get(name)
        if p and p.get("house_number") in ANGULAR_HOUSES:
            angular.append(f"{name} in H{p['house_number']}")

    if angular:
        return True, "; ".join(angular)
    return False, "Neither Venus nor Jupiter in angular house"


def _check_asc_not_late(points: dict) -> tuple[bool, str]:
    """Ascendant is not in the last 3° of its sign (27°+)."""
    asc = points.get("ASC") or points.get("Ascendant")
    if not asc:
        return False, "ASC data unavailable"

    deg = asc.get("degree", 0)
    # degree here is within-sign degree (0-29.999)
    if isinstance(deg, (int, float)) and float(deg) >= 27.0:
        return False, f"ASC at {deg:.1f}° {asc.get('sign', '')} — late degree"

    return True, f"ASC at {deg:.1f}° {asc.get('sign', '')}"
