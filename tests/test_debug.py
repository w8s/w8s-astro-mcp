"""Test the swetest parser with debug output."""

from w8s_astro_mcp.parsers.swetest import parse_swetest_output, parse_degree

# Test individual lines
test_lines = [
    "Sun             14 aq 39'38\"    1° 0'50\"",
    "Mercury         23 aq 54' 3\"    1°46'23\"",
    "Mars             8 aq 41' 8\"    0°47' 1\"",
]

print("Testing individual degree parsing:")
for line in test_lines:
    parts = line.split()
    planet = parts[0]
    position_str = " ".join(parts[1:4])
    print(f"\nPlanet: {planet}")
    print(f"Position string: '{position_str}'")
    result = parse_degree(position_str)
    print(f"Parsed: {result}")
