"""Real-world tests for house placements."""

import sys
sys.path.insert(0, '/Users/w8s/Documents/_git/w8s-astro-mcp/src')

from w8s_astro_mcp.tools.analysis_tools import find_planets_in_houses

print("=" * 60)
print("REAL-WORLD HOUSE PLACEMENT TESTS")
print("=" * 60)

# Test 1: Planet just after house cusp should be in that house
print("\n1. BASIC PLACEMENT: Planet just after cusp")
planets = {
    "Sun": {"degree": 25, "sign": "Capricorn"}  # 325° absolute
}
houses = {
    "1": {"degree": 24, "sign": "Capricorn"},   # 324° - House 1 starts here
    "2": {"degree": 20, "sign": "Aquarius"},
    "3": {"degree": 15, "sign": "Pisces"},
    "4": {"degree": 10, "sign": "Aries"},
    "5": {"degree": 5, "sign": "Taurus"},
    "6": {"degree": 0, "sign": "Gemini"},
    "7": {"degree": 24, "sign": "Cancer"},
    "8": {"degree": 20, "sign": "Leo"},
    "9": {"degree": 15, "sign": "Virgo"},
    "10": {"degree": 10, "sign": "Libra"},
    "11": {"degree": 5, "sign": "Scorpio"},
    "12": {"degree": 0, "sign": "Sagittarius"}
}

result = find_planets_in_houses(planets, houses)
print(f"   Sun at 25° Capricorn (325° abs)")
print(f"   House 1 cusp at 24° Capricorn (324° abs)")
print(f"   Placement: House {result['placements']['Sun']}")
assert result['placements']['Sun'] == 1, "Sun should be in House 1"
print("   ✓ Sun correctly placed in House 1 (just after cusp)")

print("\nAll tests passed - string keys work consistently!")
