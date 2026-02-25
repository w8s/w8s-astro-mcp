# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.1] — 2026-02-25

### Fixed

- **CLI entry point not running** — the `w8s-astro-mcp` command produced `<coroutine object main at 0x...>` and a `RuntimeWarning: coroutine 'main' was never awaited`. pip-generated console_scripts wrappers call the target function directly; pointing them at an `async def` returns a coroutine object instead of executing it. Fixed by adding a sync `run()` wrapper that calls `asyncio.run(main())` and updating `pyproject.toml` to use `w8s_astro_mcp.server:run` as the entry point. The bug existed since v0.1.0 but was masked during development because the `if __name__ == "__main__"` guard always called `asyncio.run()` directly, making `python -m w8s_astro_mcp` work while the installed CLI did not.

## [0.11.0] — 2026-02-25

### Added

- **`cast_event_chart`** — cast a chart for any date, time, and location. Optionally save with a unique label for later reference; unlabelled calls calculate and return without writing to the database.
- **`list_event_charts`** — list all saved event charts, with optional profile filter.
- **`delete_event_chart`** — permanently remove a saved event chart and all its stored positions.
- **`find_electional_windows`** — scan a time window (max 90 days) at a configurable interval and return candidate moments scored against electional criteria: `moon_not_void`, `no_retrograde_inner`, `no_retrograde_outer`, `no_retrograde_all`, `moon_waxing`, `moon_waning`, `benefic_angular`, `asc_not_late`. Results are ranked by score then by tightness.
- **`compare_charts` gains `event:<label>` resolver** — either chart may now be specified as `event:<label>` to compare against a saved event chart. Example: `chart2_date="event:wedding-2026"`.
- **Full void-of-course Moon detection** — `moon_not_void` criterion uses a geometrically correct applying-aspect check: computes the Moon's remaining degrees in its current sign and verifies whether any of the 5 major aspects (conjunction, sextile, square, trine, opposition) to any other planet falls within that window at ≤8° orb. Replaces the previous near-sign-boundary heuristic.
- **Database models** — `Event`, `EventPlanet`, `EventHouse`, `EventPoint` (4 new models, total 21).
- **AGENTS.md** — release checklist with explicit `server.json` + `pyproject.toml` sync requirement; documentation reference table.

## [0.10.2] — 2026-02-24

### Fixed

- **MCP Registry publish** — `server.json` was not updated alongside `pyproject.toml` in the 0.10.1 release, causing a duplicate-version error on the registry. Both files are now in sync at 0.10.2.

## [0.10.1] — 2026-02-24

### Fixed

- **Installation failure on macOS without CMake** — capped `timezonefinder` to `<8.0.0` to prevent it from pulling in `h3`, which requires CMake ≥3.15 to build from source. Closes [#3](https://github.com/w8s/w8s-astro-mcp/issues/3).

## [0.10.0] — 2026-02-23

### Added

- **`get_transit_history`** — query logged transits by date range, planet, and/or sign. Returns newest-first with retrograde markers. Up to 100 results per call.
- **`find_last_transit`** — scan logged transit history for the most recent occurrence of a planet matching a sign, retrograde state, and/or natal house. At least one condition required.
- **`get_ingresses`** — ephemeris-backed sign ingress and station forecast.
  - `future=True/False` for upcoming or recent events
  - `days` (1–365) sets the scan window
  - `offset` shifts the window N days from today (useful for "show me next April")
  - `extended=True` switches to a 10-year outer-planet-only mode for historical or far-future queries (e.g. "what were the ingresses during the Renaissance?")
  - Normal mode offset cap: 36,500 days (~100 years); extended mode: uncapped
- **Inline location geocoding** — `get_transits` now accepts any city name as the `location` parameter, not just saved labels. "Bangkok, Thailand", "Seattle, WA", or any Nominatim-resolvable place name works out of the box.
- **`timezonefinder` dependency** — replaces the old US-only longitude estimate with accurate IANA timezone lookup anywhere on earth. Critical for historical queries like "transits in Bangkok, April 1995" (Asia/Bangkok, not UTC).

### Changed

- 3 new Phase 4 tools bring the total to **26 MCP tools** and **302 tests**.
- Ad-hoc geocoded locations are used for the ephemeris call but not persisted to transit history — only saved profile locations are logged.
- `docs/DESIGN-DECISIONS.md` deleted — content merged into `docs/ARCHITECTURE.md`.

## [0.9.1] — 2026-02-23

### Fixed

- **`get_natal_chart` now auto-calculates on first call** — newly created profiles (and profiles migrated from v0.8) no longer return empty planets/houses. The chart is calculated via EphemerisEngine and cached to the database transparently. ([#1](https://github.com/w8s/w8s-astro-mcp/issues/1))
- **DB migration script for v0.8 → v0.9 upgrades** — `scripts/migrate_v0.8_to_v0.9.py` safely adds the six connection tables introduced in v0.9.0 to existing databases without touching existing data. ([#2](https://github.com/w8s/w8s-astro-mcp/issues/2))
- **`create_tables()` now imports all models** before calling `create_all()`, ensuring connection tables are always registered with SQLAlchemy metadata on fresh installs.

### Added

- `utils/natal_saver.py` — new module for persisting natal chart data, mirroring the `transit_logger.py` pattern (planets, houses, points in one transaction).
- `DatabaseHelper.save_natal_chart()` — idempotent method that clears stale cached natal rows and writes fresh data; safe for both first population and re-calculation after birth-data corrections.
- 2 new integration tests: save+retrieve and idempotent re-save (276 tests total).

## [0.9.0] — 2026-02-23

### Breaking Changes

- **Removed swetest binary dependency.** Users no longer need to clone, build, or PATH-configure the Swiss Ephemeris C binary. `pip install w8s-astro-mcp` is now the complete install story.
- **License changed from MIT to AGPL-3.0-or-later** due to the pysweph dependency (which is itself AGPL-3.0).

### Added

- `pysweph` dependency — Python extension wrapping the Swiss Ephemeris C library, distributed as pre-compiled wheels for macOS, Linux, and Windows.
- `EphemerisEngine` class (`utils/ephemeris.py`) — replaces swetest subprocess with direct pysweph API calls. Backward-compatible output dict; adds `is_retrograde` (from speed sign) and `absolute_position` as native fields.
- `constants.py` — `ZODIAC_SIGNS`, `PLANET_IDS`, `PLANET_NAMES`, `HOUSE_SYSTEM_CODES` shared across the codebase.
- `check_ephemeris` tool — reports current ephemeris mode (Moshier/Swiss Ephemeris), pysweph version, and precision level.
- `download_ephemeris_files` tool — two-phase download of Swiss Ephemeris `.se1` files (~2 MB) for sub-arcsecond precision; activates immediately without a server restart. Requires `confirm=true` to proceed.
- `uv.lock` for reproducible environments.

### Removed

- `swetest_integration.py`, `install_helper.py`, `parsers/swetest.py` — all swetest subprocess and text-parsing code deleted.
- `scripts/check_swetest.py` diagnostic script deleted.
- `check_swetest_installation` MCP tool replaced by `check_ephemeris`.
- Seven swetest-only test files deleted.

### Changed

- `server.py`: `init_swetest()` → `init_ephemeris()`; all `SweetestError` catches → `EphemerisError`; connection tools pass `ephemeris` engine.
- `calculation_method` default string: `"swetest"` → `"pysweph"` across all 10 model files.
- `transit_logger.py`: `is_retrograde` now populated from EphemerisEngine data (previously always `False`).
- Server integration tests now use a temp database via `DatabaseHelper(db_path=)` and are skipped in CI via `skipif(CI=true)` instead of a blanket skip.

### Fixed

- VS Code test discovery was pointing at `venv/` instead of `.venv/`.
- `SWETEST_PATH` env var removed from `.vscode/settings.json`.

## [0.8.0] — 2026-02-12

Initial public release with SQLite database, multi-profile support, composite and Davison relationship charts, and 7 profile management tools.
