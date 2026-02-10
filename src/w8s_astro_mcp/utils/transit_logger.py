"""Helper functions for saving transit lookups to database."""

from datetime import datetime
from typing import Dict, Any

from ..models import (
    TransitLookup, TransitPlanet, TransitHouse, TransitPoint,
    Location, Profile
)


def decimal_to_dms(decimal_degrees: float) -> tuple[int, int, float]:
    """Convert decimal degrees to degrees, minutes, seconds."""
    degrees = int(decimal_degrees)
    remaining = (decimal_degrees - degrees) * 60
    minutes = int(remaining)
    seconds = (remaining - minutes) * 60
    return degrees, minutes, seconds


def sign_to_absolute_position(sign: str, degree_in_sign: float) -> float:
    """Convert sign + degree to absolute position (0-360)."""
    sign_order = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    
    if sign not in sign_order:
        raise ValueError(f"Unknown sign: {sign}")
    
    sign_index = sign_order.index(sign)
    return sign_index * 30 + degree_in_sign


def save_transit_data_to_db(
    session,
    profile: Profile,
    location: Location,
    lookup_datetime: datetime,
    transit_data: Dict[str, Any],
    house_system_id: int
) -> TransitLookup:
    """
    Save complete transit data to database.
    
    Args:
        session: SQLAlchemy session
        profile: Profile for this transit lookup
        location: Location where transits were calculated
        lookup_datetime: When the transits are being analyzed (not when calculated)
        transit_data: Parsed swetest output (from parse_swetest_output)
        house_system_id: ID of house system used
    
    Returns:
        Created TransitLookup object
    """
    # Create transit lookup
    lookup = TransitLookup(
        profile_id=profile.id,
        location_id=location.id,
        location_snapshot_label=location.label,
        location_snapshot_latitude=location.latitude,
        location_snapshot_longitude=location.longitude,
        location_snapshot_timezone=location.timezone,
        lookup_datetime=lookup_datetime,
        house_system_id=house_system_id,
        calculation_method="swetest",
        ephemeris_version="2.10.03"  # TODO: Get from swetest -h output
    )
    session.add(lookup)
    session.flush()  # Get lookup.id
    
    # Create transit planets
    for planet_name, planet_data in transit_data["planets"].items():
        deg, min_, sec = decimal_to_dms(planet_data["degree"])
        abs_pos = sign_to_absolute_position(planet_data["sign"], planet_data["degree"])
        
        planet = TransitPlanet(
            transit_lookup_id=lookup.id,
            planet=planet_name,
            degree=deg,
            minutes=min_,
            seconds=sec,
            sign=planet_data["sign"],
            absolute_position=abs_pos,
            house_number=None,  # TODO: Calculate which natal house this is in
            is_retrograde=False,  # TODO: Parse from swetest output
            calculation_method="swetest"
        )
        session.add(planet)
    
    # Create transit houses
    for house_num, house_data in transit_data["houses"].items():
        deg, min_, sec = decimal_to_dms(house_data["degree"])
        abs_pos = sign_to_absolute_position(house_data["sign"], house_data["degree"])
        
        house = TransitHouse(
            transit_lookup_id=lookup.id,
            house_system_id=house_system_id,
            house_number=int(house_num),
            degree=deg,
            minutes=min_,
            seconds=sec,
            sign=house_data["sign"],
            absolute_position=abs_pos,
            calculation_method="swetest"
        )
        session.add(house)
    
    # Create transit points
    for point_name, point_data in transit_data["points"].items():
        deg, min_, sec = decimal_to_dms(point_data["degree"])
        abs_pos = sign_to_absolute_position(point_data["sign"], point_data["degree"])
        
        point = TransitPoint(
            transit_lookup_id=lookup.id,
            house_system_id=house_system_id,
            point_type=point_name,
            degree=deg,
            minutes=min_,
            seconds=sec,
            sign=point_data["sign"],
            absolute_position=abs_pos,
            calculation_method="swetest"
        )
        session.add(point)
    
    session.flush()
    return lookup
