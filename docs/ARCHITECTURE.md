# Project Architecture

## Directory Structure

```
src/w8s_astro_mcp/
├── Core MCP Server
│   ├── __init__.py
│   ├── __main__.py              # Entry point
│   └── server.py                # MCP server — tool registry & routing
│
├── Database Layer
│   ├── database.py              # SQLAlchemy engine, session management
│   └── models/                  # SQLAlchemy ORM models (17 models)
│       ├── __init__.py
│       ├── app_settings.py      # Global settings (current profile ID)
│       ├── house_system.py      # 7 house systems (Placidus, Koch, etc.)
│       ├── location.py          # Birth/home/saved locations (profile-owned)
│       ├── profile.py           # People's natal charts
│       ├── natal_planet.py      # Planet positions at birth
│       ├── natal_house.py       # House cusps at birth
│       ├── natal_point.py       # Angles (ASC, MC) at birth
│       ├── transit_lookup.py    # Record of every transit check
│       ├── transit_planet.py    # Planet positions for a transit
│       ├── transit_house.py     # House cusps for a transit
│       ├── transit_point.py     # Angles for a transit
│       ├── connection.py        # Named group of 2+ profiles
│       ├── connection_member.py # Many-to-many: connection ↔ profile
│       ├── connection_chart.py  # Cached composite/Davison chart metadata
│       ├── connection_planet.py # Planet positions in a connection chart
│       ├── connection_house.py  # House cusps in a connection chart
│       └── connection_point.py  # Angles in a connection chart
│
├── Analysis & Visualization
│   └── tools/                   # MCP tool handlers
│       ├── __init__.py
│       ├── analysis_tools.py    # Aspects, house placements
│       ├── visualization.py     # Chart drawing (matplotlib)
│       ├── profile_management.py # Profile/location CRUD tools
│       └── connection_management.py # Connection/composite/Davison tools
│
├── External Integration
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── swetest.py           # Parse swetest output into position dicts
│   └── utils/
│       ├── __init__.py
│       ├── db_helpers.py        # High-level database queries
│       ├── connection_calculator.py # Composite & Davison math
│       ├── position_utils.py    # Shared position conversion functions
│       ├── swetest_integration.py   # Swiss Ephemeris integration
│       ├── transit_logger.py    # Save transit data to database
│       ├── geocoding.py         # Location lookup (lat/long)
│       └── install_helper.py    # swetest installation help
│
```

## Data Flow

### Natal Chart Query (From Database)
```
User (Claude) → MCP Tool: get_natal_chart
                ↓
         server.py: get_natal_chart handler
                ↓
         init_db() → DatabaseHelper
                ↓
         db_helpers.get_natal_chart_data(profile)
                ↓
         SQLAlchemy queries: NatalPlanet, NatalHouse, NatalPoint
                ↓
         Format response → Return to user
```

### Transit Query (With Auto-Logging)
```
User (Claude) → MCP Tool: get_transits(date, time, location)
                ↓
         server.py: get_transits handler
                ↓
         1. DatabaseHelper: get location by label
         2. swetest_integration.get_transits(lat, lng, date, time)
         3. Parse swetest output → position dicts
         4. transit_logger.save_transit_data_to_db()
            └─> Creates: TransitLookup, TransitPlanet, TransitHouse, TransitPoint
         5. Format response → Return to user
```

### Composite Chart (Pure Math, No swetest)
```
User (Claude) → MCP Tool: get_connection_chart(id, "composite")
                ↓
         server.py → handle_connection_tool()
                ↓
         Check cache: db_helpers.get_connection_chart()
         (cache hit → format and return)
                ↓ (cache miss)
         For each member profile:
           db_helpers.get_natal_chart_data(profile)
           connection_calculator.enrich_natal_chart_for_composite()
                ↓
         connection_calculator.calculate_composite_positions()
           └─> circular mean of absolute positions per planet
               circular_mean_degrees() uses atan2 on unit vectors
                ↓
         db_helpers.save_connection_chart()
           └─> _normalize_position() coerces to standard format
           └─> Upserts ConnectionChart + planets/houses/points
                ↓
         Format response → Return to user
```

### Davison Chart (swetest Required)
```
User (Claude) → MCP Tool: get_connection_chart(id, "davison")
                ↓
         server.py → handle_connection_tool()
                ↓
         Check cache: db_helpers.get_connection_chart()
         (cache hit → format and return)
                ↓ (cache miss)
         For each member: db_helpers.get_birth_location(profile)
                ↓
         connection_calculator.calculate_davison_midpoint()
           └─> Convert local birth times → UTC via ZoneInfo
           └─> Average Unix timestamps → midpoint datetime
           └─> circular_mean_degrees() for midpoint latitude
                ↓
         swetest_integration.get_transits(midpoint lat/lng/date/time)
                ↓
         db_helpers.save_connection_chart(davison_midpoint=...)
           └─> _normalize_position() handles swetest decimal-degree format
                ↓
         Format response → Return to user
```

### Migration (One-Time Setup)
```
User runs: python scripts/migrate_config_to_sqlite.py
                ↓
         Read: ~/.w8s-astro-mcp/config.json
                ↓
         Parse birth data, locations, natal chart
                ↓
         SQLAlchemy: Create initial profile + natal chart data
                ↓
         Write: ~/.w8s-astro-mcp/astro.db
                ↓
         Done! Server now uses database automatically
```

## Key Design Decisions

### 1. Database-First Architecture
- **Old:** config.json with cached natal chart
- **New:** SQLite with normalized schema
- **Why:** Enables multi-profile, transit history, proper queries

### 2. AppSettings Table for Global State
- **Old:** Profile.is_primary boolean flag
- **New:** AppSettings.current_profile_id foreign key
- **Why:** Cleaner architecture, ON DELETE SET NULL cascade, more extensible

### 3. Profile-Owned Locations
- **Decision:** All locations require profile_id (no shared/global locations)
- **Why:** Simpler mental model, easier CASCADE deletion, clearer ownership

### 4. Separation of Concerns
- **Models:** Define data structure (SQLAlchemy ORM)
- **Database:** Handle connections, sessions
- **db_helpers:** Provide high-level queries for the server
- **transit_logger:** Handle complex transit inserts
- **connection_calculator:** Pure math — composite means, Davison midpoints
- **position_utils:** Shared low-level conversion functions
- **server.py:** Orchestrate tool routing only

### 5. Auto-Logging Transit Requests
- Every `get_transits` call logs to database automatically
- Preserves location snapshot for historical accuracy
- Builds queryable history over time
- Graceful degradation (logging failures don't break the request)

### 6. Connection Chart Caching
- Composite and Davison charts are expensive to compute and deterministic
- Results cached in `connection_charts` + child tables
- `is_valid` flag allows invalidation without deletion
- Adding/removing a connection member invalidates all charts for that connection
- Upsert pattern: recalculating replaces rows, never duplicates

### 7. Position Format Normalization (`_normalize_position`)
- Two sources produce position dicts with different shapes:
  - **Composite math:** `degree` (int), `minutes`, `seconds`, `absolute_position` all present
  - **swetest parser:** `degree` (decimal float within sign), no `minutes`/`seconds`/`absolute_position`
- `DatabaseHelper._normalize_position()` coerces either format before any DB write
- Reuses `decimal_to_dms()` and `sign_to_absolute_position()` from `position_utils.py`

### 8. `position_utils.py` — Shared Conversion Module
- `decimal_to_dms()` and `sign_to_absolute_position()` were originally defined in
  `transit_logger.py` but were needed by `db_helpers.py` too
- Extracted to `utils/position_utils.py` to eliminate cross-module dependency
  on a persistence module
- `transit_logger.py` now imports from `position_utils` (no behaviour change)

### 9. DatabaseHelper Test Mode
- `DatabaseHelper.__init__()` accepts an optional `db_path` argument
- When provided: creates the file if needed and runs `create_tables()` automatically
- When omitted: production behaviour — uses `get_database_path()`, raises on missing DB
- Enables real integration tests against isolated SQLite files without mocking

## Technology Stack

**Core:**
- Python 3.14
- MCP (Model Context Protocol) server
- SQLAlchemy 2.0 ORM
- SQLite database

**External:**
- Swiss Ephemeris (swetest binary)
- matplotlib (chart visualization)

**Dev:**
- pytest (236 tests, 2 skipped)
- git (version control)

## Database Schema

See `docs/DATABASE_SCHEMA.md` for full schema documentation.

**17 Models across 3 domains:**

Profiles & Locations (4):
1. AppSettings — global state (current profile ID)
2. HouseSystem — reference data (7 house systems)
3. Location — profile-owned locations
4. Profile — people's natal charts

Natal Charts (3):
5. NatalPlanet, 6. NatalHouse, 7. NatalPoint

Transit History (4):
8. TransitLookup, 9. TransitPlanet, 10. TransitHouse, 11. TransitPoint

Connections — Phase 7 (6):
12. Connection — named group of 2+ profiles
13. ConnectionMember — join table
14. ConnectionChart — cached chart metadata + Davison midpoint
15. ConnectionPlanet, 16. ConnectionHouse, 17. ConnectionPoint

## MCP Tools (22 total)

**Core (8):**
check_swetest_installation, setup_astro_config (deprecated), view_config,
get_natal_chart, get_transits, compare_charts, find_house_placements,
visualize_natal_chart

**Profile Management (7):**
list_profiles, create_profile, update_profile, delete_profile,
set_current_profile, add_location, remove_location

**Connection Management — Phase 7 (6):**
create_connection, list_connections, add_connection_member,
remove_connection_member, get_connection_chart, delete_connection

## Future Enhancements

### Planned:
- [ ] Transit history queries ("last month's transits")
- [ ] Statistics ("how often do I check Mercury?")
- [ ] Database self-healing tools (repair inconsistencies)

### Possible:
- [ ] Web interface for database queries
- [ ] Export transit history to CSV
- [ ] Progressive natal chart (age progression)
- [ ] More house systems (Whole Sign, Equal, etc.)
- [ ] Aspects table (natal-natal, transit-natal, transit-transit)
- [ ] Progressions and solar/lunar returns

## Contributing

When adding features:
1. Models go in `models/`
2. Database queries go in `db_helpers.py`
3. Complex inserts go in separate modules (like `transit_logger.py`)
4. Pure math/calculation logic goes in `utils/` (like `connection_calculator.py`)
5. Shared low-level conversions go in `position_utils.py`
6. MCP tool definitions and handlers go in `tools/`
7. Tool routing goes in `server.py`
8. Always add tests — unit tests for math, integration tests for db_helpers

## Testing

```bash
# Run all tests
pytest

# Connection db_helper integration tests only
pytest tests/test_connection_db_helpers.py

# Connection math tests only
pytest tests/test_connection_calculator.py

# Model tests only
pytest tests/models/

# Specific test file
pytest tests/models/test_connections.py
```

## Migration Guide

**For existing users:**
1. Run: `python scripts/migrate_config_to_sqlite.py`
2. Database created at: `~/.w8s-astro-mcp/astro.db`
3. Server automatically uses new database
4. Keep config.json as backup

**For new users:**
- No migration needed
- Server expects database to exist at `~/.w8s-astro-mcp/astro.db`
- Use migration script to create initial profile

## License

See LICENSE_NOTICE.md
