# Project Architecture

## Directory Structure

```
src/w8s_astro_mcp/
├── Core MCP Server
│   ├── __init__.py
│   ├── __main__.py              # Entry point
│   └── server.py                # MCP server implementation
│
├── Database Layer
│   ├── database.py              # SQLAlchemy engine, session management
│   └── models/                  # SQLAlchemy ORM models (10 models)
│       ├── __init__.py
│       ├── house_system.py      # 7 house systems (Placidus, Koch, etc.)
│       ├── location.py          # Birth/home/saved locations
│       ├── profile.py           # People's natal charts
│       ├── natal_planet.py      # Planet positions at birth
│       ├── natal_house.py       # House cusps at birth
│       ├── natal_point.py       # Angles (ASC, MC) at birth
│       ├── transit_lookup.py    # Record of every transit check
│       ├── transit_planet.py    # Planet positions for a transit
│       ├── transit_house.py     # House cusps for a transit
│       └── transit_point.py     # Angles for a transit
│
├── Analysis & Visualization
│   └── tools/                   # Analysis & visualization
│       ├── __init__.py
│       ├── analysis_tools.py    # Aspects, house placements
│       └── visualization.py     # Chart drawing (matplotlib)
│
├── External Integration
│   ├── parsers/                 # Parse external tool output
│   │   ├── __init__.py
│   │   └── swetest.py           # Parse swetest output
│   └── utils/                   # Utilities & Helpers
│       ├── __init__.py
│       ├── db_helpers.py        # High-level database queries
│       ├── swetest_integration.py  # Swiss Ephemeris integration
│       ├── transit_logger.py    # Save transit data to database
│       ├── geocoding.py         # Location lookup (lat/long)
│       └── install_helper.py    # swetest installation help
│
└── Deprecated
    └── config.py                # ⚠️  OLD config.json handling
                                 # Kept for backwards compatibility
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
         3. Parse swetest output
         4. 🆕 transit_logger.save_transit_data_to_db()
            └─> Creates: TransitLookup, TransitPlanet, TransitHouse, TransitPoint
         5. Format response → Return to user
```

### Migration (One-Time Setup)
```
User runs: python scripts/migrate_config_to_sqlite.py
                ↓
         Read: ~/.w8s-astro-mcp/config.json
                ↓
         Parse birth data, locations, natal chart
                ↓
         SQLAlchemy: Create 10 models worth of data
                ↓
         Write: ~/.w8s-astro-mcp/astro.db
                ↓
         Done! Server now uses database automatically
```

## Key Design Decisions

### 1. Database-First Architecture ✅
- **Old:** config.json with cached natal chart
- **New:** SQLite with normalized schema
- **Why:** Enables multi-profile, transit history, proper queries

### 2. Separation of Concerns ✅
- **Models:** Define data structure (SQLAlchemy ORM)
- **Database:** Handle connections, sessions
- **db_helpers:** Provide high-level queries
- **transit_logger:** Handle complex inserts
- **server.py:** Orchestrate everything

### 3. Auto-Logging Transit Requests ✅
- Every `get_transits` call logs to database
- Preserves location snapshot (even if location changes)
- Builds queryable history over time
- Graceful degradation (logging failures don't break requests)

### 4. Backwards Compatibility ⚠️
- `config.py` kept but deprecated
- Migration script provided
- MCP tool API unchanged
- Response format unchanged

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
- pytest (testing)
- git (version control)

## Database Schema

See `docs/DATABASE_SCHEMA.md` for full schema documentation.

**10 Models:**
1. HouseSystem (reference data)
2. Location (shared across profiles)
3. Profile (people's charts)
4. NatalPlanet, NatalHouse, NatalPoint (birth chart data)
5. TransitLookup (history of queries)
6. TransitPlanet, TransitHouse, TransitPoint (transit snapshots)

**Key Features:**
- Normalized schema (no data duplication)
- Foreign keys with proper CASCADE/RESTRICT
- Location snapshots for historical accuracy
- Ready for multi-profile support

## Future Enhancements

### Planned:
- [ ] Profile management tools (create/list/switch)
- [ ] Location management tools (add/update/remove)
- [ ] Transit history queries ("last month's transits")
- [ ] Statistics ("how often do I check Mercury?")
- [ ] Remove config.py entirely

### Possible:
- [ ] Web interface for database queries
- [ ] Export transit history to CSV
- [ ] Progressive natal chart (age progression)
- [ ] Synastry between profiles
- [ ] More house systems (Whole Sign, Equal, etc.)

## Contributing

When adding features:
1. Models go in `models/`
2. Database queries go in `db_helpers.py`
3. Complex inserts go in separate modules (like `transit_logger.py`)
4. MCP tools go in `server.py`
5. Analysis logic goes in `tools/`
6. Always add tests!

## Testing

```bash
# Run all tests
pytest

# Run database tests only
pytest tests/models/

# Run specific test file
pytest tests/models/test_house_system.py
```

## Migration Guide

**For existing users:**
1. Run: `python scripts/migrate_config_to_sqlite.py`
2. Database created at: `~/.w8s-astro-mcp/astro.db`
3. Server automatically uses new database
4. Keep config.json as backup

**For new users:**
- No migration needed
- Server expects database to exist
- Use migration script to create initial profile

## License

See LICENSE_NOTICE.md
