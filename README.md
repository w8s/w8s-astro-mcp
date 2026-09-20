<!-- mcp-name: io.github.w8s/w8s-astro-mcp -->
# w8s-astro-mcp

Personal astrological MCP server — natal charts, transits, forecasting, and relationship charts backed by a queryable SQLite database.

[![Tests](https://github.com/w8s/w8s-astro-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/w8s/w8s-astro-mcp/actions/workflows/tests.yml)
[![PyPI version](https://img.shields.io/pypi/v/w8s-astro-mcp)](https://pypi.org/project/w8s-astro-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/w8s-astro-mcp)](https://pypi.org/project/w8s-astro-mcp/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

> **⚠ Upgrading from v0.12 or earlier? Your stored charts were calculated with the wrong time zone.** Birth, event and electional times were treated as UT instead of local time, so the Ascendant, MC, houses and Moon were off. Planet signs almost always stay the same. Run `w8s-astro-recalculate --all` to see what changes, then add `--apply`. [Details](https://github.com/w8s/w8s-astro-mcp/blob/main/CHANGELOG.md)

## Features

- 🔭 **Swiss Ephemeris precision** — planetary positions via [pysweph](https://pypi.org/project/pysweph/); optional high-precision file download
- 🗂️ **Multi-profile** — manage charts for yourself, family, and friends
- 📜 **Persistent history** — every transit lookup auto-logged to SQLite; query by date, planet, or sign
- 🧭 **Transit reading** — compare today's sky to your natal chart with applying/separating direction and an estimated time of exactness; opt-in JSON output
- 🔗 **Relationship charts** — composite and Davison charts for any group of 2+ people; place today's sky in any chart's house system
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

**4. Set yourself as the owner:**

> "Set me as the owner profile."

This tells the server who you are. All tools default to your chart unless you ask about someone else. Everything is stored in `~/.w8s-astro-mcp/astro.db` (macOS/Linux) or `%USERPROFILE%\.w8s-astro-mcp\astro.db` (Windows).

## Installation

### Recommended: uvx (no install required)

`uvx` pulls the package from PyPI and runs it in an isolated environment automatically. Use the config above.

### Alternative: pip

```bash
pip install w8s-astro-mcp
```

Then use `"command": "w8s-astro-mcp"` (no `args`) in your Claude Desktop config.

### Upgrading from an earlier version

If you have an existing database from before v0.12, run the migration script once:

```bash
python scripts/migrate_owner_profile.py
```

This renames the internal `current_profile_id` column to `owner_profile_id`. Safe to run multiple times.

**Upgrading to v0.14.0 — recalculate your stored charts.** Earlier versions used the local birth time as if it were UT, so every stored natal chart has the wrong Ascendant, MC, houses and Moon. Fix it once after upgrading:

```bash
w8s-astro-recalculate --all            # dry run: shows exactly what would change
w8s-astro-recalculate --all --apply    # backs up the database first, then recalculates
# with uvx: uvx --from w8s-astro-mcp w8s-astro-recalculate --all
```

Add `--events` to include saved event charts, or `--event LABEL` to recalculate just one (repeat it for several). It is safe to run more than once, and your AI assistant will mention it after you upgrade if any stored chart still needs recalculating. The `compare_charts` changes in this release are additive: it keeps its existing output and adds one line per aspect (see the [CHANGELOG](CHANGELOG.md) if you parse that text). If you would rather not be reminded, ask it to dismiss the notice. A note on times: birth time, event time and electional dates are **local** times (converted using the location's timezone); the `time` you pass to `get_transits`, `find_house_placements` and `compare_charts` is **UT**.

**If a new install fails with `AttributeError: 'Server' object has no attribute 'list_tools'`:** upgrade to v0.12.1 or later (`uvx --refresh w8s-astro-mcp`, or `pip install -U w8s-astro-mcp`). Earlier versions did not limit which MCP SDK version they accept, so a new install picked up SDK 2.x, which this server does not support yet.

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

> "Which of today's transits to my chart are building and which are fading?"

**Other profiles:**
> "Show me Liz's natal chart."

> "What are her transits today?"

> "Compare my chart with Liz's." *(synastry)*

**House placements:**
> "Where are today's planets in my natal houses?"

> "Where does today's sky fall in our composite chart?"

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
