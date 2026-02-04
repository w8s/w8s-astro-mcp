from w8s_astro_mcp.config import ConfigManager
import tempfile
from pathlib import Path

temp_path = Path(tempfile.mktemp())
manager = ConfigManager(config_path=temp_path)

print("Initial state:")
print(f"is_configured: {manager.is_configured()}")
print(f"birth_data: {manager.get_birth_data()}")
print(f"current location: {manager.get_location('current')}")
print(f"locations dict: {manager.config.get('locations')}")

print("\nAfter setting birth data:")
manager.set_birth_data(
    "1990-05-15", "14:30", "NYC", 40.7, -74.0, "America/New_York"
)
print(f"is_configured: {manager.is_configured()}")
print(f"birth_data: {manager.get_birth_data()}")
print(f"current location: {manager.get_location('current')}")
print(f"locations dict: {manager.config.get('locations')}")
