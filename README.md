<!-- mcp-name: io.github.w8s/w8s-astro-mcp -->
# w8s-astro-mcp

Personal astrological MCP server powered by Swiss Ephemeris (swetest). Provides natal charts, transit calculations, aspect analysis, chart visualization, and relationship chart support (composite & Davison) — all backed by a queryable SQLite database.

## Features

- **Natal charts** — planetary positions, houses, and angles at birth
- **Transit calculations** — current sky positions auto-logged to history
- **Aspect analysis** — compare any two charts (natal vs natal, natal vs transits)
- **House placements** — determine which house each planet occupies
- **Chart visualization** — render natal chart wheels as PNG
- **Multi-profile** — manage charts for multiple people
- **Relationship charts** — composite and Davison charts for any group of 2+ people
- **Transit history** — every calculation stored in SQLite for future querying

## Installation

### Prerequisites

**Swiss Ephemeris (`swetest`) is required.** The server will detect if it's missing and guide you through setup.

```bash
# Clone and build Swiss Ephemeris
git clone https://github.com/aloistr/swisseph.git
cd swisseph && make

# Add to PATH (no sudo needed)
echo "export PATH=\"$(pwd):\$PATH\"" >> ~/.zshrc && source ~/.zshrc

# Verify
swetest -h
```

### Install the Server

```bash
cd ~/Documents/_git/w8s-astro-mcp
pip install -e .
```

### Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "w8s-astro-mcp": {
      "command": "w8s-astro-mcp"
    }
  }
}
```

## First-Time Setup

On first use, create your profile:

> "Create an astro profile for me — my name is [Name], born [date] at [time] in [city, state]."

Claude will use `create_profile` to set up your birth data and set you as the active profile. Everything is stored in `~/.w8s-astro-mcp/astro.db`.

**Migrating from an older version?** If you have a `config.json` from a previous install:

```bash
python scripts/migrate_config_to_sqlite.py
```

## Tools

### Core (8)

| Tool | Description |
|------|-------------|
| `check_swetest_installation` | Verify swetest is installed and working |
| `setup_astro_config` | *(deprecated)* Legacy config wizard |
| `view_config` | Show current profile and saved locations |
| `get_natal_chart` | Planetary positions, houses, and angles at birth |
| `get_transits` | Current sky positions (auto-logged to history) |
| `compare_charts` | Aspects between any two charts |
| `find_house_placements` | Which house each planet occupies |
| `visualize_natal_chart` | Render natal chart wheel as PNG |

### Profile Management (7)

| Tool | Description |
|------|-------------|
| `list_profiles` | All profiles in the database |
| `create_profile` | Add a new person's birth data |
| `update_profile` | Edit name, birth date, or birth time |
| `delete_profile` | Remove a profile (must leave connections first) |
| `set_current_profile` | Switch the active profile |
| `add_location` | Save a named location to a profile |
| `remove_location` | Delete a saved location |

### Connection Management — Phase 7 (6)

| Tool | Description |
|------|-------------|
| `create_connection` | Name a group of 2+ profiles |
| `list_connections` | All connections in the database |
| `add_connection_member` | Add a profile to a connection |
| `remove_connection_member` | Remove a profile (invalidates cached charts) |
| `get_connection_chart` | Calculate or retrieve composite/Davison chart |
| `delete_connection` | Remove a connection and all its charts |

## Database

All data lives in `~/.w8s-astro-mcp/astro.db` — a standard SQLite file you can query directly.

```bash
sqlite3 ~/.w8s-astro-mcp/astro.db

# Most-checked transit planets
SELECT planet, COUNT(*) AS checks
FROM transit_planets GROUP BY planet ORDER BY checks DESC;

# All connections
SELECT c.label, c.type FROM connections c;
```

See `docs/DATABASE_SCHEMA.md` for the full schema with ERDs and example queries.

## Architecture

See `docs/ARCHITECTURE.md` for data flow diagrams, design decisions, and the full directory structure.

**Key design choices:**
- Natal and transit positions stored as normalized rows (not JSON blobs) — fully queryable
- Every `get_transits` call auto-logs to history with a denormalized location snapshot
- Connection charts cached with an `is_valid` flag — invalidated when members change, recalculated on next access
- Position format normalized at write time via `_normalize_position()` — both composite math output and swetest decimal-degree output coerced to `degree/minutes/seconds/absolute_position`

## Testing

```bash
# Full suite
pytest

# By domain
pytest tests/models/                          # ORM model tests
pytest tests/test_connection_calculator.py    # Composite & Davison math
pytest tests/test_connection_db_helpers.py    # Integration tests (real SQLite)

# With coverage
pytest --cov=src/w8s_astro_mcp
```

236 tests, 2 skipped. See `docs/ARCHITECTURE.md` for the full test command reference.

## Roadmap

See `docs/ROADMAP.md` for planned phases including transit history queries (Phase 4), device location detection (Phase 5), event charts (Phase 8), and database self-healing tools (Phase 9).

## License

MIT
