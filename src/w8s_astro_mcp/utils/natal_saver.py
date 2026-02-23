"""Helper functions for saving natal chart data to database."""

from typing import Dict, Any

from ..models import NatalPlanet, NatalHouse, NatalPoint, Profile
from .position_utils import decimal_to_dms, sign_to_absolute_position


def save_natal_data_to_db(
    session,
    profile: Profile,
    chart_data: Dict[str, Any],
    house_system_id: int,
) -> None:
    """
    Save a calculated natal chart to the database.

    Existing natal rows for this profile are deleted first so this function
    is safe to call both for first-time population and re-calculation after a
    birth-data correction.

    Args:
        session:        Active SQLAlchemy session (caller commits).
        profile:        Profile whose natal chart is being saved.
        chart_data:     Chart dict from EphemerisEngine.get_chart().
        house_system_id: ID of the house system used for calculation.
    """
    # Clear any stale cached data for this profile
    session.query(NatalPlanet).filter_by(profile_id=profile.id).delete()
    session.query(NatalHouse).filter_by(profile_id=profile.id).delete()
    session.query(NatalPoint).filter_by(profile_id=profile.id).delete()
    session.flush()

    # Planets
    for planet_name, planet_data in chart_data["planets"].items():
        deg, min_, sec = decimal_to_dms(planet_data["degree"])
        abs_pos = sign_to_absolute_position(planet_data["sign"], planet_data["degree"])

        session.add(NatalPlanet(
            profile_id=profile.id,
            planet=planet_name,
            degree=deg,
            minutes=min_,
            seconds=sec,
            sign=planet_data["sign"],
            absolute_position=abs_pos,
            is_retrograde=planet_data.get("is_retrograde", False),
            calculation_method="pysweph",
        ))

    # Houses
    for house_num, house_data in chart_data["houses"].items():
        deg, min_, sec = decimal_to_dms(house_data["degree"])
        abs_pos = sign_to_absolute_position(house_data["sign"], house_data["degree"])

        session.add(NatalHouse(
            profile_id=profile.id,
            house_system_id=house_system_id,
            house_number=int(house_num),
            degree=deg,
            minutes=min_,
            seconds=sec,
            sign=house_data["sign"],
            absolute_position=abs_pos,
            calculation_method="pysweph",
        ))

    # Points (Asc, MC, etc.)
    for point_name, point_data in chart_data["points"].items():
        deg, min_, sec = decimal_to_dms(point_data["degree"])
        abs_pos = sign_to_absolute_position(point_data["sign"], point_data["degree"])

        session.add(NatalPoint(
            profile_id=profile.id,
            house_system_id=house_system_id,
            point_type=point_name,
            degree=deg,
            minutes=min_,
            seconds=sec,
            sign=point_data["sign"],
            absolute_position=abs_pos,
            calculation_method="pysweph",
        ))

    session.flush()
