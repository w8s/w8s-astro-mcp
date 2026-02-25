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

- [ ] Feature complete and tests passing (`venv/bin/python -m pytest`)
- [ ] `pyproject.toml` — bump `version`
- [ ] `server.json` — bump **both** `version` and `packages[0].version` to match
- [ ] `CHANGELOG.md` — add entry under new version
- [ ] Merge feature branch to `main` with `--no-ff`
- [ ] `git tag -a <version> -m "..."` and `git push origin main && git push origin <tag>`
- [ ] Wait for PyPI publish GitHub Action to complete
- [ ] `/opt/homebrew/bin/mcp-publisher publish` from repo root on `main`

> ⚠️ **server.json and pyproject.toml must always be updated together.**
> The MCP Registry validates the version against the live PyPI package — a mismatch
> causes a 400 error. A version already published to the registry cannot be republished
> (duplicate version error), so always increment even for registry-only fixes.

## Branch Strategy

- `main` — stable releases only
- `feature/*` — all new work; merge with `--no-ff`

## Key Conventions

### Session Management
Never mix `DatabaseHelper` methods with raw `get_session` calls in the same scope —
they create separate sessions and cause transaction conflicts.

### Ephemeris Import
`EphemerisEngine` and `EphemerisError` are imported **lazily** inside handler functions
(not at module top) because `swisseph` may not be installed in test environments.
Always import them after input validation so validation tests don't require swisseph.

### Test Fixtures
- All test DB fixtures must import all models before `DatabaseHelper()` so
  `Base.metadata` is complete when `create_tables()` runs.
- Seed `HOUSE_SYSTEM_SEED_DATA` into every test DB — many FK constraints depend on it.
- Use `db_helper.create_profile_with_location()` to create profiles in tests;
  don't construct `Profile` + `Location` manually (FK ordering is tricky).
- Mock `swisseph`-dependent modules via `sys.modules` injection, not `patch()` on
  the module path (the module may not be importable at all in CI).

## Common Commands

```bash
# Run all tests
venv/bin/python -m pytest

# Run one test file
venv/bin/python -m pytest tests/test_event_management.py -v

# Publish to MCP Registry (must be on main, PyPI publish must be complete)
/opt/homebrew/bin/mcp-publisher publish

# Check GitHub Actions status
/opt/homebrew/bin/gh run list --limit 5
```
