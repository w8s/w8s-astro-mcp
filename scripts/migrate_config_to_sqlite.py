#!/usr/bin/env python3
"""
Migration script: config.json → SQLite database

Migrates existing config.json data into the new normalized SQLite schema.
Creates:
- Primary profile (Todd Schragg)
- Birth location
- Home location 
- Other saved locations (Bangkok)
- Natal chart data (planets, houses, points)

Usage:
    python scripts/migrate_config_to_sqlite.py [--dry-run]
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from w8s_astro_mcp.database import initialize_database, get_session, get_database_path
from w8s_astro_mcp.models import (
    HouseSystem, Location, Profile,
    NatalPlanet, NatalHouse, NatalPoint,
    HOUSE_SYSTEM_SEED_DATA
)


def load_config() -> Dict[str, Any]:
    """Load existing config.json."""
    config_path = Path.home() / ".w8s-astro-mcp" / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path) as f:
        return json.load(f)


def decimal_to_dms(decimal_degrees: float) -> tuple[int, int, float]:
    """
    Convert decimal degrees to degrees, minutes, seconds.
    
    Example: 15.413864 → (15, 24, 49.91)
    """
    degrees = int(decimal_degrees)
    remainder = (decimal_degrees - degrees) * 60
    minutes = int(remainder)
    seconds = (remainder - minutes) * 60
    
    return degrees, minutes, seconds


def sign_to_absolute_position(sign: str, degree: float) -> float:
    """
    Convert sign + degree to absolute position (0-360°).
    
    Example: Taurus 15.413 → 45.413 (30 + 15.413)
    """
    sign_offsets = {
        "Aries": 0, "Taurus": 30, "Gemini": 60, "Cancer": 90,
        "Leo": 120, "Virgo": 150, "Libra": 180, "Scorpio": 210,
        "Sagittarius": 240, "Capricorn": 270, "Aquarius": 300, "Pisces": 330
    }
    
    return sign_offsets[sign] + degree


def migrate_config(dry_run: bool = False):
    """Main migration function."""
    
    print("=" * 60)
    print("Config.json → SQLite Migration")
    print("=" * 60)
    
    # Load config
    print("\n📖 Loading config.json...")
    config = load_config()
    print(f"✅ Config loaded")
    
    # Initialize database
    db_path = get_database_path()
    print(f"\n🗄️  Database: {db_path}")
    
    if db_path.exists() and not dry_run:
        response = input("⚠️  Database already exists. Overwrite? [y/N] ")
        if response.lower() != 'y':
            print("❌ Migration cancelled")
            return
        db_path.unlink()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be saved")
        return
    
    engine = initialize_database(db_path)
    print("✅ Database initialized")
    
    with get_session(engine) as session:
        
        # 1. Seed house systems
        print("\n1️⃣  Seeding house systems...")
        for data in HOUSE_SYSTEM_SEED_DATA:
            session.add(HouseSystem(**data))
        session.flush()
        placidus = session.query(HouseSystem).filter_by(code='P').first()
        print(f"   ✅ 7 house systems seeded")
        
        # 2. Create birth location
        print("\n2️⃣  Creating birth location...")
        birth_data = config["birth_data"]["location"]
        birth_location = Location(
            label="Birth",
            latitude=birth_data["latitude"],
            longitude=birth_data["longitude"],
            timezone=birth_data["timezone"]
        )
        session.add(birth_location)
        session.flush()
        print(f"   ✅ Birth location: {birth_location.label}")
        
        # 3. Create home location
        print("\n3️⃣  Creating home location...")
        home_data = config["locations"]["home"]
        home_location = Location(
            label="Home",
            latitude=home_data["latitude"],
            longitude=home_data["longitude"],
            timezone=home_data["timezone"],
            is_current_home=True
        )
        session.add(home_location)
        session.flush()
        print(f"   ✅ Home location: {home_location.label}")
        
        # 4. Create other locations
        print("\n4️⃣  Creating saved locations...")
        location_count = 0
        for key, loc_data in config["locations"].items():
            if key in ["birth", "home", "current"]:
                continue
            
            location = Location(
                label=loc_data["name"],
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
                timezone=loc_data["timezone"]
            )
            session.add(location)
            location_count += 1
            print(f"   ✅ {loc_data['name']}")
        
        session.flush()
        print(f"   ✅ {location_count} additional locations created")
        
        # 5. Create primary profile
        print("\n5️⃣  Creating primary profile...")
        birth = config["birth_data"]
        profile = Profile(
            name="Todd Schragg",
            birth_date=birth["date"],
            birth_time=birth["time"],
            birth_location_id=birth_location.id,
            is_primary=True,
            preferred_house_system_id=placidus.id
        )
        session.add(profile)
        session.flush()
        print(f"   ✅ Profile: {profile.name}")
        
        # 6. Create natal planets
        print("\n6️⃣  Creating natal planets...")
        natal_chart = config["natal_chart"]
        planet_count = 0
        
        for planet_name, planet_data in natal_chart["planets"].items():
            deg, min_, sec = decimal_to_dms(planet_data["degree"])
            abs_pos = sign_to_absolute_position(planet_data["sign"], planet_data["degree"])
            
            planet = NatalPlanet(
                profile_id=profile.id,
                planet=planet_name,
                degree=deg,
                minutes=min_,
                seconds=sec,
                sign=planet_data["sign"],
                absolute_position=abs_pos,
                calculation_method="swetest",
                calculated_at=datetime.fromisoformat(natal_chart["cached_at"])
            )
            session.add(planet)
            planet_count += 1
        
        session.flush()
        print(f"   ✅ {planet_count} planets created")
        
        # 7. Create natal houses
        print("\n7️⃣  Creating natal houses...")
        house_count = 0
        
        for house_num, house_data in natal_chart["houses"].items():
            deg, min_, sec = decimal_to_dms(house_data["degree"])
            abs_pos = sign_to_absolute_position(house_data["sign"], house_data["degree"])
            
            house = NatalHouse(
                profile_id=profile.id,
                house_system_id=placidus.id,
                house_number=int(house_num),
                degree=deg,
                minutes=min_,
                seconds=sec,
                sign=house_data["sign"],
                absolute_position=abs_pos,
                calculation_method="swetest",
                calculated_at=datetime.fromisoformat(natal_chart["cached_at"])
            )
            session.add(house)
            house_count += 1
        
        session.flush()
        print(f"   ✅ {house_count} houses created")
        
        # 8. Create natal points
        print("\n8️⃣  Creating natal points...")
        point_count = 0
        
        for point_name, point_data in natal_chart["points"].items():
            deg, min_, sec = decimal_to_dms(point_data["degree"])
            abs_pos = sign_to_absolute_position(point_data["sign"], point_data["degree"])
            
            point = NatalPoint(
                profile_id=profile.id,
                house_system_id=placidus.id,
                point_type=point_name,
                degree=deg,
                minutes=min_,
                seconds=sec,
                sign=point_data["sign"],
                absolute_position=abs_pos,
                calculation_method="swetest",
                calculated_at=datetime.fromisoformat(natal_chart["cached_at"])
            )
            session.add(point)
            point_count += 1
        
        session.flush()
        print(f"   ✅ {point_count} points created")
        
        # Commit everything
        session.commit()
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 60)
        print(f"\n📊 Summary:")
        print(f"   • House systems: 7")
        print(f"   • Locations: {2 + location_count} (birth, home, +{location_count})")
        print(f"   • Profiles: 1 (primary)")
        print(f"   • Natal planets: {planet_count}")
        print(f"   • Natal houses: {house_count}")
        print(f"   • Natal points: {point_count}")
        print(f"\n📁 Database: {db_path}")
        print(f"💾 Size: {db_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    
    try:
        migrate_config(dry_run)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
