"""Test the swetest parser with real output."""

from w8s_astro_mcp.parsers.swetest import parse_swetest_output

# Sample swetest output (using generic coordinates)
test_output = """
date (dmy) 3.2.2026 greg.   12:00:00 UT		version 2.10.03
UT:  2461075.000000000     delta t: 68.888787 sec
TT:  2461075.000797324
geo. long -74.006000, lat 40.713000, alt 0.000000
Epsilon (t/m)     23°26'18"   23°26' 9"
Nutation           0° 0' 7"    0° 0' 9"
Houses system P (Placidus) for long= -74°00'22", lat=  40°42'47"
Sun             14 aq 39'38"    1° 0'50"
Moon             4 vi 54'57"   13°34'41"
Mercury         23 aq 54' 3"    1°46'23"
Venus           21 aq 18'49"    1°15'15"
Mars             8 aq 41' 8"    0°47' 1"
Jupiter         17 cn  5'18"   -0° 6'22"
Saturn          28 pi 53'24"    0° 6' 3"
Uranus          27 ta 27'36"   -0° 0' 2"
Neptune          0 ar 12'36"    0° 1'43"
Pluto            3 aq 46'34"    0° 1'54"
house  1        23 cp 22' 8"  403°44'50"
house  2         6 pi 55'37"  489°46'17"
house  3        16 ar 31' 9"  437°12'52"
house  4        15 ta 56'55"  361°17'40"
house  5         8 ge 58'35"  324°25'17"
house  6        29 ge 58'22"  331° 9'32"
house  7        23 cn 22' 8"  403°44'50"
house  8         6 vi 55'37"  489°46'17"
house  9        16 li 31' 9"  437°12'52"
house 10        15 sc 56'55"  361°17'40"
house 11         8 sa 58'35"  324°25'17"
house 12        29 sa 58'22"  331° 9'32"
Ascendant       23 cp 22' 8"  403°44'50"
MC              15 sc 56'55"  361°17'40"
"""

if __name__ == "__main__":
    result = parse_swetest_output(test_output)
    
    import json
    print(json.dumps(result, indent=2))
