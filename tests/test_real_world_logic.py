"""Integration tests - Real astrological scenarios."""

import sys
sys.path.insert(0, '/Users/w8s/Documents/_git/w8s-astro-mcp/src')

from w8s_astro_mcp.tools.analysis_tools import (
    get_absolute_position,
    calculate_aspect_angle,
    identify_aspect,
    compare_charts
)

print("=" * 60)
print("REAL-WORLD ASTROLOGICAL TESTS")
print("=" * 60)

# Test 1: Known opposition - Signs exactly opposite should be 180°
print("\n1. OPPOSITION: Sun in Aries vs Moon in Libra")
sun_aries = get_absolute_position(15, "Aries")      # 15°
moon_libra = get_absolute_position(15, "Libra")     # 195°
angle = calculate_aspect_angle(sun_aries, moon_libra)
print(f"   Sun at 15° Aries = {sun_aries}° absolute")
print(f"   Moon at 15° Libra = {moon_libra}° absolute")
print(f"   Angle between them = {angle}°")
assert angle == 180, f"Opposite signs at same degree should be 180°, got {angle}"
aspect = identify_aspect(angle)
assert aspect["name"] == "opposition", f"Should be opposition, got {aspect['name']}"
print(f"   ✓ Correctly identified as {aspect['name']}")

# Test 2: Known trine - Fire signs 120° apart
print("\n2. TRINE: Mars in Aries vs Jupiter in Leo")
mars_aries = get_absolute_position(10, "Aries")     # 10°
jupiter_leo = get_absolute_position(10, "Leo")      # 130°
angle = calculate_aspect_angle(mars_aries, jupiter_leo)
print(f"   Mars at 10° Aries = {mars_aries}° absolute")
print(f"   Jupiter at 10° Leo = {jupiter_leo}° absolute")
print(f"   Angle between them = {angle}°")
assert angle == 120, f"Fire signs at same degree should be 120°, got {angle}"
aspect = identify_aspect(angle)
assert aspect["name"] == "trine", f"Should be trine, got {aspect['name']}"
print(f"   ✓ Correctly identified as {aspect['name']}")

# Test 3: Known square - Cardinal signs 90° apart
print("\n3. SQUARE: Venus in Cancer vs Saturn in Libra")
venus_cancer = get_absolute_position(20, "Cancer")   # 110°
saturn_libra = get_absolute_position(20, "Libra")    # 200°
angle = calculate_aspect_angle(venus_cancer, saturn_libra)
print(f"   Venus at 20° Cancer = {venus_cancer}° absolute")
print(f"   Saturn at 20° Libra = {saturn_libra}° absolute")
print(f"   Angle between them = {angle}°")
assert angle == 90, f"Square signs at same degree should be 90°, got {angle}"
aspect = identify_aspect(angle)
assert aspect["name"] == "square", f"Should be square, got {aspect['name']}"
print(f"   ✓ Correctly identified as {aspect['name']}")

# Test 4: Orb test - Near aspect vs out of orb
print("\n4. ORB LIMITS: Testing conjunction boundaries")
# 7° apart - within 8° orb
within_orb = identify_aspect(7)
print(f"   7° apart: {within_orb['name'] if within_orb else 'No aspect'}")
assert within_orb is not None and within_orb["name"] == "conjunction"
print(f"   ✓ 7° correctly within conjunction orb")

# 9° apart - outside 8° orb
outside_orb = identify_aspect(9)
print(f"   9° apart: {outside_orb['name'] if outside_orb else 'No aspect'}")
assert outside_orb is None
print(f"   ✓ 9° correctly outside conjunction orb")

# Test 5: Chart comparison - Multiple aspects
print("\n5. CHART COMPARISON: Finding multiple aspects")
chart1 = {
    "planets": {
        "Sun": {"degree": 10, "sign": "Aries"},
        "Moon": {"degree": 10, "sign": "Leo"}  # Trine to Sun
    },
    "metadata": {"date": "2000-01-01"}
}
chart2 = {
    "planets": {
        "Mars": {"degree": 10, "sign": "Libra"},  # Opposition to Sun
        "Venus": {"degree": 10, "sign": "Leo"}     # Conjunction to Moon
    },
    "metadata": {"date": "2000-02-01"}
}

result = compare_charts(chart1, chart2)
print(f"   Found {len(result['aspects'])} aspects")

# Should find: Sun opp Mars, Sun trine Venus, Moon conj Venus, Moon trine Mars
assert len(result['aspects']) >= 3, f"Should find at least 3 aspects"
print(f"   ✓ Found multiple valid aspects")

# Verify specific aspects exist
aspect_names = [a['aspect'] for a in result['aspects']]
assert 'opposition' in aspect_names, "Should find opposition"
assert 'trine' in aspect_names, "Should find trine"
print(f"   ✓ Includes expected aspect types: {set(aspect_names)}")

print("\n" + "=" * 60)
print("✅ ALL REAL-WORLD TESTS PASSED")
print("=" * 60)
print("\nThese tests validate actual astrological relationships,")
print("not just that the code runs without errors.")
