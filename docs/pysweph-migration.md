# pysweph Migration Plan

**Branch:** `feature/pysweph-migration`  
**Goal:** Replace the `swetest` binary subprocess approach with `pysweph` — a Python
extension that compiles the Swiss Ephemeris C library directly into a Python wheel.
Users will no longer need to install or locate any binary.

---

## Why

- `swetest` requires building from source (C compiler, `make`, PATH config)
- This is a non-starter for non-technical users
- `pysweph` ships pre-compiled wheels for macOS (arm64 + x86_64), Linux, and Windows
- `pip install pysweph` is the entire install story — no binary, no PATH, no source

## Which Package

**Use:** [`pysweph`](https://github.com/sailorfe/pysweph) (community fork)  
**Not:** `pyswisseph` (original, maintainer unresponsive since mid-2025)  
**PyPI:** https://pypi.org/project/pysweph/  
**Import name is the same:** `import swisseph as swe` (fork preserves this)

## License Implication

`pysweph` is AGPL-3.0, which requires the consuming project to also be AGPL-3.0
(or a compatible license). The current `w8s-astro-mcp` license is MIT, which is
**not** AGPL-compatible.

**Action required:** Change `pyproject.toml` license from `MIT` to `AGPL-3.0-or-later`
before merging this branch to main.

---

## What Changes

### Files Deleted
| File | Reason |
|------|--------|
| `src/w8s_astro_mcp/utils/swetest_integration.py` | Replaced by `ephemeris.py` |
| `src/w8s_astro_mcp/utils/install_helper.py` | No binary to install |
| `src/w8s_astro_mcp/parsers/swetest.py` | No text output to parse |

### Files Created
| File | Purpose |
|------|---------|
| `src/w8s_astro_mcp/utils/ephemeris.py` | New ephemeris engine using pysweph API |

### Files Modified
| File | Change |
|------|--------|
| `src/w8s_astro_mcp/server.py` | Replace `SweetestIntegration` / `InstallationHelper` imports and `init_swetest()` with `init_ephemeris()`; update `check_swetest_installation` tool |
| `src/w8s_astro_mcp/utils/transit_logger.py` | Change `calculation_method` from `"swetest"` to `"pysweph"` |
| `src/w8s_astro_mcp/tools/connection_management.py` | Update Davison chart call site to new API |
| `pyproject.toml` | Add `pysweph` dependency; change license to AGPL-3.0-or-later |
| `README.md` | Remove swetest install instructions; update prerequisites |
| `docs/AGENTS.md` | Update development notes |

### Files With Minor String Updates Only (no logic change)
These files have `default="swetest"` in SQLAlchemy model columns. The string is
stored in the database as a calculation method audit trail — change to `"pysweph"`.

| File |
|------|
| `src/w8s_astro_mcp/models/natal_planet.py` |
| `src/w8s_astro_mcp/models/natal_house.py` |
| `src/w8s_astro_mcp/models/natal_point.py` |
| `src/w8s_astro_mcp/models/transit_planet.py` |
| `src/w8s_astro_mcp/models/transit_house.py` |
| `src/w8s_astro_mcp/models/transit_point.py` |
| `src/w8s_astro_mcp/models/transit_lookup.py` |
| `src/w8s_astro_mcp/models/connection_planet.py` |
| `src/w8s_astro_mcp/models/connection_house.py` |
| `src/w8s_astro_mcp/models/connection_point.py` |

Note: `house_system.py` has a comment referencing the swetest `-house` flag — update
the comment to reference pysweph's `swe.houses()` function instead.

---

## New API: ephemeris.py

The new module replaces the subprocess + text-parsing approach with direct function
calls. Here is the conceptual mapping:

### Old approach (swetest)
```python
# Build shell command
cmd = ["swetest", "-b3.2.2026", "-ut12:00", "-p0123456789",
       "-house-90.2,38.6,P", "-fPZS"]
result = subprocess.run(cmd, capture_output=True, text=True)
# Parse multi-line text output...
data = parse_swetest_output(result.stdout)
```

### New approach (pysweph)
```python
import swisseph as swe

swe.set_ephe_path(None)       # use built-in Moshier ephemeris (no files needed)
jd = swe.julday(2026, 2, 3, 12.0)   # Julian Day

# Planets
for planet_id in PLANET_IDS:
    xx, ret = swe.calc_ut(jd, planet_id)
    longitude = xx[0]   # ecliptic longitude 0-360°
    speed = xx[3]       # deg/day (negative = retrograde)

# Houses and angles (ASC, MC)
cusps, ascmc = swe.houses(jd, latitude, longitude, b"P")
# cusps[1..12] = house cusp longitudes
# ascmc[0] = Ascendant, ascmc[1] = MC
```

### Key pysweph concepts

**Julian Day** — pysweph (like all Swiss Ephemeris interfaces) works in Julian Day
numbers, not calendar dates. Use `swe.julday(year, month, day, hour_decimal)` to
convert. Hour is decimal: 12:30 = 12.5.

**Planet IDs** — integer constants: `swe.SUN=0`, `swe.MOON=1`, `swe.MERCURY=2`,
`swe.VENUS=3`, `swe.MARS=4`, `swe.JUPITER=5`, `swe.SATURN=6`, `swe.URANUS=7`,
`swe.NEPTUNE=8`, `swe.PLUTO=9`.

**`swe.calc_ut(jd, planet)`** — returns `(xx, ret_flags)` where `xx` is a 6-element
tuple: `[longitude, latitude, distance, speed_long, speed_lat, speed_dist]`. We use
`xx[0]` (longitude, 0-360°) and `xx[3]` (speed, negative = retrograde).

**`swe.houses(jd, lat, lng, hsys)`** — `hsys` is a bytes literal like `b"P"` for
Placidus. Returns `(cusps, ascmc)`. `cusps` is a 13-element tuple (index 0 unused,
indices 1-12 = house cusps). `ascmc` has ASC at index 0, MC at index 1.

**Ephemeris files** — calling `swe.set_ephe_path(None)` activates the built-in
Moshier ephemeris, which requires no external files and is accurate to within
~1 arcminute for planets (sufficient for astrological use). Users who want
sub-arcsecond precision can download `.se1` files and set their path.

**Retrograde** — detected via speed: `is_retrograde = xx[3] < 0`.

**Longitude → sign** — divide absolute longitude (0-360°) by 30 to get sign index.
Signs are ordered Aries=0 through Pisces=11. Degree within sign = `longitude % 30`.

### Output data structure

The new `EphemerisEngine.get_chart()` method will return the same dict structure
that `parse_swetest_output()` currently returns, so all downstream consumers
(transit_logger, connection_management, db_helpers) require no logic changes:

```python
{
    "planets": {
        "Sun": {"sign": "Aquarius", "degree": 14.66, "formatted": "14°39'", 
                "absolute_position": 314.66, "is_retrograde": False},
        ...
    },
    "houses": {
        "1": {"sign": "Capricorn", "degree": 24.39, "formatted": "24°23'",
              "absolute_position": 294.39},
        ...  # keys "1" through "12" as strings
    },
    "points": {
        "Ascendant": {"sign": "Capricorn", "degree": 24.39, "formatted": "24°23'",
                      "absolute_position": 294.39},
        "MC": {...}
    },
    "metadata": {
        "date": "2026-02-03",
        "time": "12:00:00",
        "latitude": 38.637,
        "longitude": -90.263,
        "house_system": "Placidus",
        "ephemeris": "moshier"   # or "sweph" if .se1 files used
    }
}
```

Note: `is_retrograde` and `absolute_position` are **additions** vs the old swetest
output — previously these required extra calculation. pysweph gives us retrograde
directly from speed, and absolute position is the raw longitude value.

---

## Updated `check_swetest_installation` Tool

The tool name will change to `check_ephemeris` (or we keep the name for backwards
compatibility but update its behavior). It should now report:

- pysweph version installed
- Whether Moshier (built-in) or Swiss Ephemeris files are in use
- Path to `.se1` files if configured (via `SE_EPHE_PATH` env var)

---

## Implementation Order

Work through files in this order to keep things buildable at each step:

1. **`pyproject.toml`** — add `pysweph` dependency, update license
2. **`src/w8s_astro_mcp/utils/ephemeris.py`** — create new engine (TDD: write tests first)
3. **`src/w8s_astro_mcp/server.py`** — swap imports and init logic
4. **`src/w8s_astro_mcp/utils/transit_logger.py`** — update `calculation_method` string
5. **`src/w8s_astro_mcp/tools/connection_management.py`** — update Davison call site
6. **Model files** — update `default="swetest"` → `default="pysweph"` (10 files)
7. **Delete** `swetest_integration.py`, `install_helper.py`, `parsers/swetest.py`
8. **`README.md`** — remove swetest prerequisites section, simplify install
9. **Tests** — update/add tests for new ephemeris module; verify existing test suite passes

---

## Testing Strategy

- Existing tests that mock swetest subprocess calls will need updating
- New unit tests for `ephemeris.py` should verify:
  - Julian Day conversion accuracy
  - Correct sign assignment at sign boundaries (e.g. 29°59' Aries vs 0°00' Taurus)
  - Retrograde detection
  - House cusp output matches expected structure
  - Output dict structure is backward-compatible with old swetest parser output
- Integration: run `get_natal_chart` and `get_transits` end-to-end after migration

---

## Version Bump

This is a breaking change in the dependency model (removes swetest requirement).
Bump to **0.9.0** on merge to main.

---

## Open Questions

- [ ] Keep tool named `check_swetest_installation` (backwards compat) or rename to
      `check_ephemeris`? Leaning rename since the swetest name will confuse users.
- [ ] Expose `SE_EPHE_PATH` configuration in settings for power users who want
      higher-precision `.se1` files?
- [ ] Update `ephemeris_version` field in `TransitLookup` to report the pysweph
      version string at runtime rather than hardcoding `"2.10.03"`.
