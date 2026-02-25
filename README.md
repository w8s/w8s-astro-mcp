<!-- mcp-name: io.github.w8s/w8s-astro-mcp -->
# w8s-astro-mcp

Personal astrological MCP server — natal charts, transits, forecasting, and relationship charts backed by a queryable SQLite database.

[![Tests](https://github.com/w8s/w8s-astro-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/w8s/w8s-astro-mcp/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/w8s-astro-mcp)](https://pypi.org/project/w8s-astro-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/w8s-astro-mcp)](https://pypi.org/project/w8s-astro-mcp/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

## Features

- 🔭 **Swiss Ephemeris precision** — planetary positions via [pysweph](https://pypi.org/project/pysweph/); optional high-precision file download
- 🗂️ **Multi-profile** — manage charts for yourself, family, and friends
- 📜 **Persistent history** — every transit lookup auto-logged to SQLite; query by date, planet, or sign
- 🔗 **Relationship charts** — composite and Davison charts for any group of 2+ people
- 🗓️ **Event & electional tools** — cast charts for any moment; scan windows for auspicious times

## Quick Start

**1. Install [uv](https://docs.astral.sh/uv/) if you don't have it** — see the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) for your platform.

**2. Add to your Claude Desktop config:**

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

**3. Restart Claude Desktop, then create your profile:**

> "Create an astro profile for me — my name is [Name], born [YYYY-MM-DD] at [HH:MM] in [City, State]."

That's it. Everything is stored in `~/.w8s-astro-mcp/astro.db` (macOS/Linux) or `%USERPROFILE%\.w8s-astro-mcp\astro.db` (Windows).

## Installation

### Recommended: uvx (no install required)

`uvx` pulls the package from PyPI and runs it in an isolated environment automatically. Use the config above.

### Alternative: pip

```bash
pip install w8s-astro-mcp
```

Then use `"command": "w8s-astro-mcp"` (no `args`) in your Claude Desktop config.

### Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (for `uvx` method) or pip
- Claude Desktop (or any MCP-compatible client)

## Use Cases

**Get started:**
> "Create an astro profile for me — my name is [Name], born [YYYY-MM-DD] at [HH:MM] in [City, State]."

> "Show me my natal chart."

**Daily practice:**
> "What are my transits for today?"

> "When was Mercury last retrograde?"

> "What major transits are coming up in the next 90 days?"

**Relationships:**
> "Create a profile for my partner, born [YYYY-MM-DD] at [HH:MM] in [City, State]."

> "Create a connection called 'Us' and show me our synastry."

> "Calculate a Davison chart for us."

**Events & planning:**
> "Cast a chart for the moment we got married — [date] at [time] in [city]."

> "Find auspicious times to sign a contract next month — Moon not void, Mercury direct."

**History & research:**
> "When was Jupiter last in Taurus?"

> "Show me all my transit lookups from last month."

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Directory structure, full tool list, data flow, design decisions |
| [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Full ERD, all models, example SQL queries |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phase history and planned work |
| [docs/TESTING_MCP.md](docs/TESTING_MCP.md) | How to configure Claude Desktop and smoke-test the server |

## Contributing & Development

See [AGENTS.md](AGENTS.md) for the development workflow, testing commands, branch strategy, and release checklist.

## Questions & Bugs

Open an issue on [GitHub](https://github.com/w8s/w8s-astro-mcp/issues).

## License

[AGPL-3.0](LICENSE)
