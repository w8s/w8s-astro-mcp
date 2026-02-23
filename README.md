<!-- mcp-name: io.github.w8s/w8s-astro-mcp -->
# w8s-astro-mcp

[![Tests](https://github.com/w8s/w8s-astro-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/w8s/w8s-astro-mcp/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/w8s-astro-mcp)](https://pypi.org/project/w8s-astro-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/w8s-astro-mcp)](https://pypi.org/project/w8s-astro-mcp/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

Personal astrological MCP server using the Swiss Ephemeris via pysweph. Provides natal charts, transit calculations, aspect analysis, chart visualization, and relationship chart support (composite & Davison) — all backed by a queryable SQLite database.

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

### Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "w8s-astro-mcp": {
      "command": "uvx",
      "args": ["w8s-astro-mcp"]
    }
  }
}
```

`uvx` pulls the package from PyPI and runs it in an isolated environment — no manual install needed. If you don't have `uv`, install it with:

```bash
brew install uv
```

### Alternative: pip install

```bash
pip install w8s-astro-mcp
```

Then use `"command": "w8s-astro-mcp"` (no `args`) in your Claude Desktop config.

## First-Time Setup

On first use, create your profile:

> "Create an astro profile for me — my name is [Name], born [date] at [time] in [city, state]."

Claude will use `create_profile` to set up your birth data and set you as the active profile. Everything is stored in `~/.w8s-astro-mcp/astro.db`.

## Tools

### Core (8)

| Tool | Description |
|------|-------------|
| `check_ephemeris` | Report ephemeris mode (Moshier/Swiss Ephemeris), pysweph version, and precision |
| `download_ephemeris_files` | Download Swiss Ephemeris .se1 files for higher precision (optional) |
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
- Position format normalized at write time via `_normalize_position()` — both composite math output and pysweph decimal-degree output coerced to `degree/minutes/seconds/absolute_position`

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

274 tests. See `docs/ARCHITECTURE.md` for the full test command reference.

## Roadmap

See `docs/ROADMAP.md` for planned phases including transit history queries (Phase 4), device location detection (Phase 5), event charts (Phase 8), and database self-healing tools (Phase 9).

## License

AGPL-3.0
