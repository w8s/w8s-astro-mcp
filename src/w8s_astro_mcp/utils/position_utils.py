"""Shared position conversion utilities.

Low-level math for converting between astrological position formats.
Used by transit_logger, db_helpers, and any future module that stores
or compares planetary positions.
"""


SIGN_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def decimal_to_dms(decimal_degrees: float) -> tuple[int, int, float]:
    """Convert decimal degrees to (degrees, minutes, seconds).

    Args:
        decimal_degrees: Decimal degree value within a sign (0.0–30.0)
            or any non-negative float.

    Returns:
        (degrees: int, minutes: int, seconds: float)

    Example:
        decimal_to_dms(14.66) -> (14, 39, 36.0)
    """
    degrees = int(decimal_degrees)
    remaining = (decimal_degrees - degrees) * 60
    minutes = int(remaining)
    seconds = (remaining - minutes) * 60
    return degrees, minutes, seconds


def sign_to_absolute_position(sign: str, degree_in_sign: float) -> float:
    """Convert a sign name + degree-within-sign to absolute ecliptic position (0–360°).

    Args:
        sign: Full sign name (e.g., 'Aquarius')
        degree_in_sign: Decimal degrees within the sign (0.0–30.0)

    Returns:
        Absolute ecliptic longitude in degrees (0.0–360.0)

    Raises:
        ValueError: If sign is not a recognised zodiac sign name.

    Example:
        sign_to_absolute_position("Aquarius", 14.66) -> 314.66
    """
    if sign not in SIGN_ORDER:
        raise ValueError(f"Unknown sign: {sign}")
    return SIGN_ORDER.index(sign) * 30 + degree_in_sign
