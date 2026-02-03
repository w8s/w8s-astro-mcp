from w8s_astro_mcp.parsers.swetest import parse_degree

# Test the problematic house 1 line
test = "23 cp 22' 8\""
print(f"Input: '{test}'")
result = parse_degree(test)
print(f"Result: {result}")
