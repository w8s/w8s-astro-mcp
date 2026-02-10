"""Test database models can be created and used."""

import sys
sys.path.insert(0, '/Users/w8s/Documents/_git/w8s-astro-mcp/src')

from pathlib import Path
import os
from datetime import datetime, timezone

from w8s_astro_mcp.database import initialize_database, get_session, get_database_path
from w8s_astro_mcp.models import Profile, TransitLookup

print("=" * 70)
print("DATABASE MODELS TEST")
print("=" * 70)

# Use a test database
test_db = Path("/tmp/test_astro_models.db")
if test_db.exists():
    os.remove(test_db)

# Initialize database with models
print("\n1. INITIALIZING DATABASE")
print("-" * 70)
engine = initialize_database(test_db, echo=False)
print(f"✅ Database created at: {test_db}")

# Create a test profile
print("\n2. CREATING PROFILE")
print("-" * 70)
with get_session(engine) as session:
    profile = Profile(
        name="Todd Schragg",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_name="St. Louis, MO",
        birth_latitude=38.627003,
        birth_longitude=-90.199402,
        birth_timezone="America/Chicago",
        is_primary=True
    )
    session.add(profile)
    session.flush()  # Get the ID
    profile_id = profile.id
    print(f"✅ Created profile: {profile}")
    print(f"   ID: {profile_id}")
    print(f"   Name: {profile.name}")
    print(f"   Birth: {profile.birth_date} at {profile.birth_time}")
    print(f"   Location: {profile.birth_location_name}")
    print(f"   Primary: {profile.is_primary}")

# Test natal chart caching
print("\n3. TESTING NATAL CHART CACHING")
print("-" * 70)
with get_session(engine) as session:
    profile = session.query(Profile).filter_by(id=profile_id).first()
    
    # No chart yet
    print(f"Initial chart: {profile.get_natal_chart()}")
    assert profile.get_natal_chart() is None, "Should start with no chart"
    
    # Cache a chart
    test_chart = {
        "planets": {"Sun": {"degree": 15.5, "sign": "Taurus"}},
        "houses": {"1": {"degree": 11.7, "sign": "Scorpio"}},
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
    }
    profile.set_natal_chart(test_chart)
    session.flush()
    
    print(f"✅ Cached natal chart")
    print(f"   Cached at: {profile.natal_chart_cached_at}")
    
    # Retrieve chart
    retrieved = profile.get_natal_chart()
    assert retrieved is not None, "Chart should be cached"
    assert retrieved["planets"]["Sun"]["degree"] == 15.5, "Chart data should match"
    print(f"✅ Retrieved natal chart successfully")

# Create a transit lookup
print("\n4. CREATING TRANSIT LOOKUP")
print("-" * 70)
with get_session(engine) as session:
    profile = session.query(Profile).filter_by(id=profile_id).first()
    
    transit_data = {
        "planets": {"Moon": {"degree": 23.1, "sign": "Cancer"}},
        "houses": {"10": {"degree": 5.2, "sign": "Leo"}},
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
    }
    
    lookup = TransitLookup(
        profile_id=profile.id,
        transit_date="2026-02-09",
        transit_time="12:00",
        location_name="Richardson, TX",
        location_latitude=32.9483,
        location_longitude=-96.7299,
        location_timezone="America/Chicago",
        notes="Testing transit lookup creation"
    )
    lookup.set_transit_data(transit_data)
    session.add(lookup)
    session.flush()
    
    print(f"✅ Created transit lookup: {lookup}")
    print(f"   ID: {lookup.id}")
    print(f"   Profile: {lookup.profile.name}")
    print(f"   Transit date: {lookup.transit_date} at {lookup.transit_time}")
    print(f"   Location: {lookup.location_name}")
    print(f"   Notes: {lookup.notes}")

# Test relationship
print("\n5. TESTING PROFILE → TRANSIT RELATIONSHIP")
print("-" * 70)
with get_session(engine) as session:
    profile = session.query(Profile).filter_by(id=profile_id).first()
    
    print(f"Profile: {profile.name}")
    print(f"Transit lookups: {len(profile.transit_lookups)}")
    for lookup in profile.transit_lookups:
        print(f"  - {lookup.transit_date} at {lookup.transit_time} ({lookup.location_name})")
    
    assert len(profile.transit_lookups) == 1, "Should have 1 transit lookup"
    print("✅ Relationship working correctly")

# Test to_dict methods
print("\n6. TESTING TO_DICT METHODS")
print("-" * 70)
with get_session(engine) as session:
    profile = session.query(Profile).filter_by(id=profile_id).first()
    lookup = session.query(TransitLookup).first()
    
    profile_dict = profile.to_dict()
    print(f"Profile dict keys: {list(profile_dict.keys())}")
    assert "id" in profile_dict
    assert "name" in profile_dict
    assert "birth_location" in profile_dict
    assert profile_dict["has_natal_chart"] is True
    print("✅ Profile.to_dict() working")
    
    lookup_dict = lookup.to_dict()
    print(f"Transit lookup dict keys: {list(lookup_dict.keys())}")
    assert "id" in lookup_dict
    assert "profile_name" in lookup_dict
    assert "location" in lookup_dict
    print("✅ TransitLookup.to_dict() working")

# Cleanup
print("\n7. CLEANUP")
print("-" * 70)
if test_db.exists():
    os.remove(test_db)
    print(f"✅ Test database removed")

print("\n" + "=" * 70)
print("ALL TESTS PASSED ✅")
print("=" * 70)
