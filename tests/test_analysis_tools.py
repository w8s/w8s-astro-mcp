"""Test script for analysis_tools.py"""

import sys
sys.path.insert(0, '/Users/w8s/Documents/_git/w8s-astro-mcp/src')

from w8s_astro_mcp.tools.analysis_tools import (
    compare_charts,
    find_planets_in_houses,
    format_aspect_report,
    format_house_report,
    get_absolute_position
)

# Test data - sample natal chart
natal_chart = {
    "planets": {
        "Sun": {"degree": 14.66, "sign": "Aquarius"},
        "Moon": {"degree": 23.90, "sign": "Aquarius"},
        "Mercury": {"degree": 5.12, "sign": "Pisces"},
        "Venus": {"degree": 28.45, "sign": "Capricorn"},
        "Mars": {"degree": 12.33, "sign": "Aries"}
    },
    "houses": {
        "1": {"degree": 10.5, "sign": "Scorpio"},
        "2": {"degree": 8.2, "sign": "Sagittarius"},
        "3": {"degree": 6.8, "sign": "Capricorn"},
        "4": {"degree": 7.1, "sign": "Aquarius"},
        "5": {"degree": 9.3, "sign": "Pisces"},
        "6": {"degree": 12.5, "sign": "Aries"},
        "7": {"degree": 10.5, "sign": "Taurus"},
        "8": {"degree": 8.2, "sign": "Gemini"},
        "9": {"degree": 6.8, "sign": "Cancer"},
        "10": {"degree": 7.1, "sign": "Leo"},
        "11": {"degree": 9.3, "sign": "Virgo"},
        "12": {"degree": 12.5, "sign": "Libra"}
    },
    "metadata": {
        "date": "1973-02-03",
        "time": "12:00:00"
    }
}

# Test data - sample transit chart
transit_chart = {
    "planets": {
        "Sun": {"degree": 17.80, "sign": "Aquarius"},
        "Moon": {"degree": 8.50, "sign": "Cancer"},
        "Mercury": {"degree": 23.90, "sign": "Aquarius"},
        "Venus": {"degree": 15.20, "sign": "Pisces"},
        "Mars": {"degree": 14.75, "sign": "Aries"}
    },
    "metadata": {
        "date": "2026-02-07",
        "time": "12:00:00"
    }
}

print("=" * 60)
print("Testing Analysis Tools")
print("=" * 60)

# Test 1: Compare charts (natal vs transits)
print("\n1. COMPARING CHARTS (Natal vs Transits)")
print("-" * 60)
result = compare_charts(natal_chart, transit_chart)
print(format_aspect_report(result))

# Test 2: Find planets in houses
print("\n2. FINDING PLANETS IN HOUSES")
print("-" * 60)
house_result = find_planets_in_houses(
    natal_chart["planets"],
    natal_chart["houses"]
)
print(format_house_report(house_result))

# Test 3: Test absolute position calculation
print("\n3. TESTING ABSOLUTE POSITION CALCULATION")
print("-" * 60)
test_positions = [
    ("Sun", 14.66, "Aquarius"),
    ("Moon", 0.0, "Aries"),
    ("Mars", 29.99, "Pisces")
]

for name, degree, sign in test_positions:
    abs_pos = get_absolute_position(degree, sign)
    print(f"{name}: {degree:.2f}° {sign} = {abs_pos:.2f}° absolute")

print("\n" + "=" * 60)
print("Tests completed successfully!")
print("=" * 60)
