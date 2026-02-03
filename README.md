# w8s-astro-mcp

Astrological transit MCP server using Swiss Ephemeris (swetest).

## Features

### Phase 1: MVP (Current)
- Parse swetest output for daily transits
- Calculate house positions
- Detect mechanical changes (stelliums, anaretic degrees, sign changes)
- Rich JSON data return for LLM analysis
- Interactive setup wizard for birth data

## Installation

```bash
# From repo directory
pip install -e .
```

## Requirements

- Python 3.10+
- Swiss Ephemeris (`swetest` binary installed and in PATH)
  - macOS: `brew install swisseph` (if available) or download from https://www.astro.com/swisseph/
  - Linux: Install from package manager or source
  - Windows: Download binary from https://www.astro.com/swisseph/

## Configuration

First run will prompt for:
- Birth date, time, and location
- Current location (optional)
- House system preference (default: Placidus)

Configuration stored in `~/.config/w8s-astro-mcp/config.json`

## Usage

Add to your MCP settings (typically `~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "w8s-astro-mcp": {
      "command": "w8s-astro-mcp"
    }
  }
}
```

## Tools

### `setup_astro_config`
Interactive wizard to configure birth data and preferences.

### `get_daily_transits`
Get transit data for a specific date with rich metadata.

**Parameters:**
- `date` (optional): Date in YYYY-MM-DD format (default: today)
- `location` (optional): Named location or "current" (default: current)

**Returns:** Rich JSON with planetary positions, houses, stelliums, and detected shifts.

### `get_transit_markdown`
Get formatted markdown table for Obsidian daily notes.

**Parameters:**
- `date` (optional): Date in YYYY-MM-DD format (default: today)
- `location` (optional): Named location or "current" (default: current)

**Returns:** Markdown formatted transit tables.

### `check_major_shifts`
Detect significant astrological events.

**Parameters:**
- `date` (optional): Date to check (default: today)
- `days_ahead` (optional): How many days to look ahead (default: 3)

**Returns:** List of major shifts (sign changes, stations, stelliums, etc.)

## Roadmap

See ROADMAP.md for planned features.

## License

MIT
