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

### Prerequisites

**Swiss Ephemeris (swetest) is required.** If not installed, the MCP server will guide you through setup.

### Quick Start

```bash
# 1. Install this package
cd ~/Documents/_git/w8s-astro-mcp
pip install -e .

# 2. Install Swiss Ephemeris
# The MCP server will detect if swetest is missing and provide
# interactive installation instructions when you first use it.
```

### Manual Swiss Ephemeris Installation

If you prefer to install swetest manually:

```bash
# Clone Swiss Ephemeris to a directory of your choice
git clone https://github.com/aloistr/swisseph.git
cd swisseph

# Build
make

# Add to PATH (choose one method):

# Method A: Symlink to system bin (requires sudo)
sudo ln -s $(pwd)/swetest /usr/local/bin/swetest

# Method B: Add to shell PATH (no sudo needed)
echo "export PATH=\"$(pwd):\$PATH\"" >> ~/.bashrc
source ~/.bashrc

# Verify
swetest -h  # Should show version 2.10.03
```

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


## Testing

### Quick Tests (No Dependencies)
```bash
pytest tests/ -k "not real" -v  # 33+ unit tests with mocking
```

### Full Integration Tests (Requires swetest)
```bash
# Install Swiss Ephemeris first
brew install swisseph  # macOS

# Then run integration tests
pytest tests/test_swetest_real.py -v
```

See `tests/README_TESTING.md` for detailed testing strategy.
