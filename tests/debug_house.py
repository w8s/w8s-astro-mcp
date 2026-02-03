import re
from w8s_astro_mcp.parsers.swetest import parse_swetest_output

# Test just house 1
test = "house  1        23 cp 22' 8\"  403°44'50\""
print(f"Test line: '{test}'")

# Try the regex
match = re.match(r"house\s+(\d+)\s+(.*)", test)
if match:
    house_num = int(match.group(1))
    rest = match.group(2).strip()
    print(f"House num: {house_num}")
    print(f"Rest: '{rest}'")
    
    parts = rest.split()
    print(f"Parts: {parts}")
    
    position_str = " ".join(parts[0:3])
    print(f"Position string (first 3): '{position_str}'")
    
    # Try taking 4 parts
    position_str = " ".join(parts[0:4])
    print(f"Position string (first 4): '{position_str}'")
