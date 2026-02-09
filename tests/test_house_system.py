"""Test HouseSystem model in isolation."""

from pathlib import Path
import os
import sys

# Add to path
sys.path.insert(0, '/Users/w8s/Documents/_git/w8s-astro-mcp/src')

# Import in correct order
from w8s_astro_mcp.models.house_system import HouseSystem, HOUSE_SYSTEM_SEED_DATA
from w8s_astro_mcp.database import initialize_database, get_session

print("=" * 60)
print("HOUSE SYSTEM MODEL TEST")
print("=" * 60)

# Use test DB
test_db = Path('/tmp/test_house_system.db')
if test_db.exists():
    os.remove(test_db)

# Initialize (creates table)
engine = initialize_database(test_db)
print(f"\n✅ Database created at: {test_db}")

# Seed house systems
with get_session(engine) as session:
    for data in HOUSE_SYSTEM_SEED_DATA:
        hs = HouseSystem(**data)
        session.add(hs)

print(f"✅ Seeded {len(HOUSE_SYSTEM_SEED_DATA)} house systems")

# Query them back
with get_session(engine) as session:
    systems = session.query(HouseSystem).all()
    print(f"✅ Retrieved {len(systems)} house systems\n")
    
    for hs in systems:
        marker = '⭐' if hs.is_default else '  '
        print(f"{marker} {hs.code}: {hs.name}")
    
    # Test to_dict
    default = session.query(HouseSystem).filter_by(is_default=True).first()
    print(f"\n✅ Default system:")
    print(f"   {default.to_dict()}")

# Cleanup
os.remove(test_db)
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED - HouseSystem working!")
print("=" * 60)
