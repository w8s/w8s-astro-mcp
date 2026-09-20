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
- [ ] `server.json` — bump **both** `version` and `packages[0].version` to match (`scripts/bump_version.py <version>` does all three plus the CHANGELOG heading)
- [ ] `CHANGELOG.md` — add entry under new version
- [ ] Merge to `main` with a merge commit, not a squash (`gh pr merge --merge`, or `--no-ff` locally)
- [ ] `git tag -a <version> <merge-commit> -m "..."` and `git push origin <version>` (the tag triggers the PyPI publish)
- [ ] Wait for PyPI publish GitHub Action to complete (also auto-creates GitHub Release from CHANGELOG.md; preview the notes first with `python scripts/release_notes.py <version>`)
- [ ] **Update the main clone** (`/Users/w8s/Documents/_git/w8s-astro-mcp`): `git pull --ff-only` on `main`, then check that `server.json` carries the released version in both places. `mcp-publisher` publishes the `server.json` in the directory it runs from, so a stale clone re-submits the old version and fails as a duplicate. If you edited `server.json` by hand there, discard it first (`git checkout -- server.json`); the pull brings the same change
- [ ] `/opt/homebrew/bin/mcp-publisher publish` from that repo root on `main`

> The main clone is also what Claude Desktop runs, so this pull updates the live server's working tree.
> `git diff --stat HEAD origin/main -- src` (before pulling) shows whether any runtime code changes.

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
| `docs/DATABASE_SCHEMA.md` | Full ERD, all 22 models, constraint rules, example queries |
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
See `tests/test_find_house_placements.py` and `tests/test_compare_charts.py` for the pattern.

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

### Local Times vs UT
`EphemerisEngine.get_chart()` takes **UT**. Never pass it a local time.
- **Local inputs are converted.** A birth time (`Profile.birth_time` + the birth location's timezone),
  a `cast_event_chart` time, and `find_electional_windows` dates are local wall-clock times. Convert
  them with `utils/timezones.py` (`utc_engine_args`, `local_to_utc`, `utc_to_local`) before calling the
  engine, and keep the stored/displayed values local. Do not hand-roll offset arithmetic; `zoneinfo`
  handles historical DST.
- **Transit tools take UT.** The `time` argument of `get_transits`, `find_house_placements` and
  `compare_charts` is UT (`"09:00"` is 04:00 in US Central daylight time), and anything derived from a
  snapshot (for example `compare_charts`' `exact_utc`) is UT too. Say so in tool descriptions and docs.
- Before v0.14.0 the local inputs were passed through unconverted; `w8s-astro-recalculate` repairs
  charts stored that way (see ARCHITECTURE.md decision #16).

### Tool Output Is a Public Surface
The server is published to PyPI and the MCP Registry, and `uvx` users pick up releases without
choosing to upgrade. Treat default tool output as an interface:
- Change it **additively**: keep existing lines byte-for-byte and append new information, or put
  it behind an opt-in parameter (see `compare_charts`: original four lines per aspect, one line
  appended, `include_angles` / `format` opt-in).
- Keep old parameters working as aliases rather than renaming them (`planets_only`).
- Add a regression test that pins the unchanged lines, and list the change under **Changed** in
  the CHANGELOG with a before/after example.
- Presentation (glyphs, wikilinks, which results are worth showing) belongs to the caller; the
  server returns data.

### Telling the AI and the User
- **Durable rules** go in `SERVER_INSTRUCTIONS` (sent when the AI connects). Keep it short.
- **Facts about the user's data** go in tool results as a `Data notice:` (see `utils/chart_health.py`),
  never in the instructions. A notice is factual, names no one, offers options and asks the assistant to
  get the user's consent before acting. It is a **separate content block** (the original output stays
  byte-identical) and, for JSON output, a `notices` list. It is rate-limited, and a failure to compute
  it must never break the tool call.
- **Let the user dismiss it.** Store the dismissal in the database (a small new table, which `create_all` adds
  to existing databases — no migration), keyed to what the user has seen so a *different* problem brings the
  notice back. Expose it as a tool (`dismiss_data_notice`, `undo=true` to reverse), not a config file.
- Prefer a **condition** ("stored charts differ from a correct calculation") over an event ("first call
  after upgrade"): it repeats until the problem is fixed and needs no stored state.
- A release that changes results or requires user action is a **minor** bump pre-1.0. Put the plain-language
  headline and the fix at the top of the CHANGELOG entry — the GitHub Release body is built from it.

### Dependency Bounds
`mcp` is bounded `<2`: SDK 2.x removed the `Server.list_tools()` / `call_tool()` decorators the server is
built on, and an unbounded `mcp>=1.0.0` broke every fresh install at import. Bound the major version of any
dependency the server is built on. `tests/test_dependency_pins.py` guards the `mcp` bound. Dependabot is
told not to propose the two updates known to break installs (`.github/dependabot.yml`: `mcp` major
versions, and `timezonefinder` 8.x, which pulls in a compiled dependency that breaks installs without
CMake; see the 0.11.2 changelog), and `tests/test_dependabot_config.py` keeps those rules from being dropped.
Still look at any other Dependabot proposal that loosens a bound before merging it.

### Test Fixtures
- All test DB fixtures must import all models before `DatabaseHelper()` so
  `Base.metadata` is complete when `create_tables()` runs.
- `initialize_database()` automatically seeds `HOUSE_SYSTEM_SEED_DATA` — do not
  add manual house system seeding in fixtures; it will cause UNIQUE constraint errors.
- Use `db_helper.create_profile_with_location()` to create profiles in tests;
  don't construct `Profile` + `Location` manually (FK ordering is tricky).
- Mock `swisseph`-dependent modules via `sys.modules` injection, not `patch()` on
  the module path (the module may not be importable at all in CI).
- 577 tests total (573 at v0.14.0, 364 at v0.12.1, 361 at v0.12.0).

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
