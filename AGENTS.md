# AGENTS.md — Development Notes for AI Assistants

This file contains conventions, workflows, and checklists for anyone (human or AI)
working on w8s-astro-mcp. Keep it updated as the project evolves.

## Repository Layout

```
src/w8s_astro_mcp/
  server.py          # MCP server entry point, tool dispatch
  database.py        # SQLAlchemy engine, session management
  models/            # One file per model (Event, Profile, Location, etc.)
  tools/             # One file per tool group (natal, transits, connections, events…)
  utils/             # db_helpers.py, ephemeris.py, electional.py, geocoding.py
tests/               # pytest, one file per tool group
server.json          # MCP Registry metadata — MUST match pyproject.toml version
pyproject.toml       # Package metadata and dependencies
CHANGELOG.md         # Keep a Changelog format
```

## Release Checklist

Every release requires **all of the following** — missing any one will cause a broken
release or a failed MCP Registry publish.

- [ ] Feature complete and tests passing (`.venv/bin/python -m pytest`)
- [ ] `pyproject.toml` — bump `version`
- [ ] `server.json` — bump **both** `version` and `packages[0].version` to match
- [ ] `CHANGELOG.md` — add entry under new version
- [ ] Merge feature branch to `main` with `--no-ff`
- [ ] `git tag -a <version> -m "..."` and `git push origin main && git push origin <tag>`
- [ ] Wait for PyPI publish GitHub Action to complete (also auto-creates GitHub Release from CHANGELOG.md)
- [ ] `/opt/homebrew/bin/mcp-publisher publish` from repo root on `main`

> ⚠️ **server.json and pyproject.toml must always be updated together.**
> The MCP Registry validates the version against the live PyPI package — a mismatch
> causes a 400 error. A version already published to the registry cannot be republished
> (duplicate version error), so always increment even for registry-only fixes.

## Documentation

Key reference docs live in `docs/` — read these before making significant changes:

| File | What's in it |
|------|-------------|
| `README.md` | User-facing overview: features, installation, tools table, database examples |
| `CHANGELOG.md` | Every user-visible change, following Keep a Changelog format |
| `docs/ARCHITECTURE.md` | Directory structure, data flow diagrams, all design decisions with rationale |
| `docs/DATABASE_SCHEMA.md` | Full ERD, all 21 models, constraint rules, example queries |
| `docs/ROADMAP.md` | Phase history (1–8 complete), Phase 9 status, future ideas |
| `docs/TESTING_MCP.md` | How to configure Claude Desktop and smoke-test the server |

When adding a phase or significant feature, update **all** of these that apply:
- `README.md` — add new tools to the tools table and update the Features section
- `CHANGELOG.md` — add an entry under the new version
- `docs/ROADMAP.md` — mark completed items, add new planned items
- `docs/ARCHITECTURE.md` — if you add modules, change data flow, or make a design decision
- `docs/DATABASE_SCHEMA.md` — if you add or change models
- `docs/PHASE-N-PLANNING.md` — create this before starting a new phase

## Branch Strategy

- `main` — stable releases only
- `feature/*` — all new work; merge with `--no-ff`

## Key Conventions

### Owner Profile Identity Model
The server has a single stable concept of "who the human is": `AppSettings.owner_profile_id`.
This is set once via `setup_owner` and should never change during normal operation.
All tools default to the owner profile when no `profile_id` is supplied.

**Never reintroduce a "current profile" or session-switching concept.** The old
`set_current_profile` / `current_profile_id` model was replaced in v0.12.0 because
it conflated the operator's identity with the subject of a query. Other profiles are
objects to query *about* — they are not personas to switch into.

For tools that can target any profile, add an optional `profile_id` parameter that
defaults to the owner. For tools that compare two natal charts (synastry), use
`chart1_profile_id` and `chart2_profile_id` as separate parameters.

### Handler Extraction for Testability
Complex tool handlers should be extracted into standalone `async def handle_*()`
functions defined **above** `@app.list_tools()`. The MCP dispatcher calls these with
a single `await`:

```python
# Standalone — directly importable and testable
async def handle_find_house_placements(arguments: dict) -> list[TextContent]:
    ...

# Dispatcher delegates
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    ...
    elif name == "find_house_placements":
        return await handle_find_house_placements(arguments)
```

Tests import and call `handle_*()` directly — no need to pierce the MCP decorator.
See `tests/test_find_house_placements.py` for the pattern.

### Entry Points Must Be Sync
`[project.scripts]` entry points in `pyproject.toml` are called directly by pip-generated
wrappers — no `await`, no `asyncio.run()`. Never point an entry point at an `async def`.
Always use a sync wrapper that calls `asyncio.run(the_async_fn())`. See `server.run()`
and `tests/test_entrypoint.py` for the pattern and regression tests.
Never mix `DatabaseHelper` methods with raw `get_session` calls in the same scope —
they create separate sessions and cause transaction conflicts.

### Ephemeris Import
`EphemerisEngine` and `EphemerisError` are imported **lazily** inside handler functions
(not at module top) because `swisseph` may not be installed in test environments.
Always import them after input validation so validation tests don't require swisseph.

### Test Fixtures
- All test DB fixtures must import all models before `DatabaseHelper()` so
  `Base.metadata` is complete when `create_tables()` runs.
- `initialize_database()` automatically seeds `HOUSE_SYSTEM_SEED_DATA` — do not
  add manual house system seeding in fixtures; it will cause UNIQUE constraint errors.
- Use `db_helper.create_profile_with_location()` to create profiles in tests;
  don't construct `Profile` + `Location` manually (FK ordering is tricky).
- Mock `swisseph`-dependent modules via `sys.modules` injection, not `patch()` on
  the module path (the module may not be importable at all in CI).
- 356 tests total as of v0.12.0.

## Common Commands

```bash
# Run full test suite (macOS/Linux)
.venv/bin/python -m pytest

# Windows
.venv\Scripts\python -m pytest

# Run one test file
.venv/bin/python -m pytest tests/test_event_management.py -v

# Run by domain
.venv/bin/python -m pytest tests/models/
.venv/bin/python -m pytest tests/test_connection_calculator.py

# With coverage
.venv/bin/python -m pytest --cov=src/w8s_astro_mcp

# Publish to MCP Registry (must be on main, PyPI publish must be complete)
/opt/homebrew/bin/mcp-publisher publish

# Check GitHub Actions status
/opt/homebrew/bin/gh run list --limit 5
```
