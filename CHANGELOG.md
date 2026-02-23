# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] — 2026-02-23

### Breaking Changes
- **Removed swetest binary dependency.** Users no longer need to clone, build,
  or PATH-configure the Swiss Ephemeris C binary. `pip install w8s-astro-mcp`
  is now the complete install story.
- **License changed from MIT to AGPL-3.0-or-later** due to the pysweph
  dependency (which is itself AGPL-3.0).

### Added
- `pysweph` dependency — Python extension wrapping the Swiss Ephemeris C
  library, distributed as pre-compiled wheels for macOS, Linux, and Windows.
- `EphemerisEngine` class (`utils/ephemeris.py`) — replaces swetest subprocess
  with direct pysweph API calls. Backward-compatible output dict; adds
  `is_retrograde` (from speed sign) and `absolute_position` as native fields.
- `constants.py` — `ZODIAC_SIGNS`, `PLANET_IDS`, `PLANET_NAMES`,
  `HOUSE_SYSTEM_CODES` shared across the codebase.
- `check_ephemeris` tool — reports current ephemeris mode (Moshier/Swiss
  Ephemeris), pysweph version, and precision level.
- `download_ephemeris_files` tool — two-phase download of Swiss Ephemeris
  `.se1` files (~2 MB) for sub-arcsecond precision; activates immediately
  without a server restart. Requires `confirm=true` to proceed.
- `uv.lock` for reproducible environments.

### Removed
- `swetest_integration.py`, `install_helper.py`, `parsers/swetest.py` —
  all swetest subprocess and text-parsing code deleted.
- `scripts/check_swetest.py` diagnostic script deleted.
- `check_swetest_installation` MCP tool replaced by `check_ephemeris`.
- Seven swetest-only test files deleted.

### Changed
- `server.py`: `init_swetest()` → `init_ephemeris()`; all `SweetestError`
  catches → `EphemerisError`; connection tools pass `ephemeris` engine.
- `calculation_method` default string: `"swetest"` → `"pysweph"` across all
  10 model files.
- `transit_logger.py`: `is_retrograde` now populated from EphemerisEngine
  data (previously always `False`).
- Server integration tests now use a temp database via `DatabaseHelper(db_path=)`
  and are skipped in CI via `skipif(CI=true)` instead of a blanket skip.

### Fixed
- VS Code test discovery was pointing at `venv/` instead of `.venv/`.
- `SWETEST_PATH` env var removed from `.vscode/settings.json`.

## [0.8.0] — 2026-02-12

Initial public release with SQLite database, multi-profile support,
composite and Davison relationship charts, and 7 profile management tools.
