# Server.py Database Integration TODO

## Current Status

✅ **COMPLETE:**
- 10 SQLAlchemy models built and tested
- Migration script created and run successfully
- Data migrated from config.json to SQLite
- DatabaseHelper class created with query methods

❌ **PENDING:**
- Server.py still uses Config class
- Need to refactor swetest_integration.py
- Need to add auto-logging for transit requests

## Why Server Refactor is Complex

**Problem:** `swetest_integration.py` is tightly coupled to the `Config` class:

```python
class SweetestIntegration:
    def __init__(self, config: Config, swetest_path: str = "swetest"):
        self.config = config
        
    def get_current_transits(self, location_name: str = "current"):
        location = self.config.get_location(location_name)  # ← Depends on Config
```

This means we can't just swap Config for DatabaseHelper in server.py - we need to refactor swetest_integration.py first.

## Refactoring Strategy

### Phase 1: Decouple swetest_integration.py from Config

**BEFORE:**
```python
swetest = SweetestIntegration(config)
result = swetest.get_current_transits(location_name="home")
```

**AFTER:**
```python
swetest = SweetestIntegration()
location = db.get_location_by_label("home")
result = swetest.get_transits_for_location(
    location=location.to_dict(),
    date_str="2026-02-09",
    time_str="12:00",
    house_system_code="P"
)
```

### Phase 2: Update server.py tools

**Replace:**
- `init_config()` → `init_db()`
- `config.get_birth_data()` → `db.get_primary_profile()`
- `config.get_location()` → `db.get_location_by_label()`
- `config.get_natal_chart()` → `db.get_natal_chart_data()`

**Add new tools:**
- `list_profiles` - Show all profiles
- `create_profile` - Add new person's chart
- `list_locations` - Show saved locations
- `add_location` - Save new location
- `set_current_home` - Change default location

### Phase 3: Auto-logging for transits

**When get_transits tool is called:**
1. Parse date/time/location from arguments
2. Call swetest to get transit data
3. **NEW:** Call `db.save_transit_lookup()` to log the request
4. Return formatted response

This creates a history of every transit check in the database.

## Implementation Order

1. ✅ Create DatabaseHelper with query methods
2. ⬜ Refactor `swetest_integration.py`:
   - Remove Config dependency
   - Accept location as dict parameter
   - Accept house_system_code parameter
3. ⬜ Update `server.py`:
   - Replace `init_config()` with `init_db()`
   - Update `get_natal_chart` tool
   - Update `get_transits` tool
   - Update `setup_astro_config` tool (or remove if not needed)
   - Update `view_config` tool
4. ⬜ Add transit logging:
   - Implement `save_transit_lookup()` fully
   - Add helper to parse swetest output into transit tables
   - Call after every transit request
5. ⬜ Add new profile management tools
6. ⬜ Deprecate/remove Config class entirely
7. ⬜ Update tests to use database instead of config.json

## Files to Modify

- `src/w8s_astro_mcp/swetest_integration.py` - Remove Config dependency
- `src/w8s_astro_mcp/server.py` - Use DatabaseHelper instead of Config
- `src/w8s_astro_mcp/db_helpers.py` - Complete save_transit_lookup()
- `tests/` - Update tests to use database

## Estimated Effort

- **Phase 1:** 30-45 minutes (swetest refactor)
- **Phase 2:** 45-60 minutes (server.py refactor)
- **Phase 3:** 30-45 minutes (transit logging)
- **Total:** ~2-3 hours

## Notes

- Config.json can remain as fallback for now
- No breaking changes to MCP tool API
- Database schema already supports everything we need
- Can do this incrementally (Phase 1 → test → Phase 2 → test → Phase 3)
