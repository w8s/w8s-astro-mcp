# v0.13.0 Planning — Transit Direction, Chart Labels, JSON Output

**Status:** spec approved 2026-09-19; implementation on `feature/transit-direction-json`.
**Lifecycle:** delete after release, folding the durable parts into `ARCHITECTURE.md`
(decision #15), the same way `PHASE-8-PLANNING.md` was handled.

## Goal

Make `compare_charts` usable for day-to-day transit reading:

1. Say whether each aspect is **applying** (building) or **separating** (fading), with an
   estimate of when it is/was exact.
2. Say which **chart** each body belongs to (natal vs. transit), so natal angles are never
   confused with the angles of the transit sky.
3. Offer **machine-readable JSON** output alongside the existing text.

Presentation (arrows, wikilinks, the "major aspect / slow planet / within ~2°" rule for showing
angle hits) is deliberately **not** in the server. It lives in the briefing template.

## Findings that shaped scope

- Claude Desktop launches the server from this repo's `.venv` (editable install), so the main
  working tree *is* the live server. Feature work happens in a separate git worktree.
- `tests/test_analysis_tools.py` and `tests/test_real_world_logic.py` contain no test functions
  (print scripts), so `compare_charts` had effectively no automated coverage. New real tests are
  required; the old scripts are left alone (cleanup is a follow-up).
- CI runs Python 3.10–3.12; local dev is 3.14. Code must stay 3.10-compatible.
- Swiss Ephemeris already returns each planet's speed; `_calc_planets` discards it after deriving
  `is_retrograde`. `identify_aspect` already carries a placeholder `"applying": None`.
- `compare_charts` never passes a location to `get_chart_for_date`, so transit-chart angles use the
  owner's current home location.
- **The `time` argument is interpreted as UT** (`swe.julday`, no timezone conversion). Any
  clock time derived from a snapshot must be converted from UT by the consumer. See Addendum.

## Behavior

1. **Ephemeris** — planet dicts gain `speed` (signed degrees/day). No DB or schema change.
   Natal charts and saved event charts are read from the DB and carry no speed.
2. **Motion** — new helper computes, for an aspect between body1 (chart1) and body2 (chart2):
   - `applying`: `True` / `False` / `None`
   - `days_to_exact`: signed float (negative = exact already passed)
   - `exact_utc`: ISO-8601 UTC timestamp, or `None`

   A body with no speed is treated as fixed. Both `None` when neither body has speed, or when the
   relative speed is under 0.001°/day (stationary). Linear estimate from instantaneous speed:
   unreliable for the Moon and near stations (documented).
3. **Chart labels** — `metadata.chart1` / `chart2` carry `kind` (`natal`, `transit`,
   `event:<label>`), optional `name`, `date`, `time`. Each body carries `chart` (label) and
   `chart_index` (1 or 2). If both kinds are equal (synastry), labels use the profile name, and fall
   back to "chart 1"/"chart 2" when names are missing or identical.
4. **`include_angles`** — `none` (default) | `natal` | `transit` | `both`. `natal` includes points
   (Ascendant, MC, …) only from charts whose kind is `natal`; `transit` only from `transit`;
   `both` from every chart. `planets_only` remains as an alias (`true` → `none`,
   `false` → `both`); if both are supplied, `include_angles` wins.
5. **`format`** — `text` (default) | `json`.
6. **Handler** — extracted to `handle_compare_charts()` per AGENTS.md; enums validated with clear
   errors.

## Compatibility contract

- Default call (`format=text`, no `include_angles`) returns the **same lines as 0.12.0**, byte for
  byte, plus **one appended line per aspect**:

  ```
  **Neptune** Quincunx **Mars**
    Neptune: 24.45° Sagittarius
    Mars: 24.79° Cancer
    Orb: 0.34°
    Neptune = natal · Mars = transit · separating · exact ~0.6 days ago (≈ 2026-09-18 19:24 UT)
  ```
- Header lines and the "no aspects" message are unchanged.
- `planets_only` keeps working. No parameter, key, or tool is removed or renamed.
- Version: minor bump (0.12.0 → 0.13.0). No deprecation of `text`.
- ~2–4 PyPI downloads/day, and `uvx` users can pick up releases unpinned, so nothing may break for
  callers who do not opt in.

## JSON shape

```json
{
  "metadata": {
    "chart1": {"kind": "natal", "label": "natal", "name": null, "date": "1981-05-06", "time": "00:50:00"},
    "chart2": {"kind": "transit", "label": "transit", "name": null, "date": "2026-09-19", "time": "09:00"},
    "orb_multiplier": 0.6,
    "include_angles": "natal",
    "total_aspects": 27
  },
  "aspects": [{
    "aspect": "quincunx", "exact_angle": 150, "actual_angle": 149.66,
    "orb": 0.34, "orb_used": 1.8,
    "applying": false, "days_to_exact": -0.57, "exact_utc": "2026-09-18T19:24:00Z",
    "body1": {"name": "Neptune", "chart": "natal", "chart_index": 1,
              "sign": "Sagittarius", "degree": 24.45, "absolute": 264.45, "speed": null},
    "body2": {"name": "Mars", "chart": "transit", "chart_index": 2,
              "sign": "Cancer", "degree": 24.79, "absolute": 114.79, "speed": 0.6}
  }]
}
```

Numbers stay numbers (units documented in the tool schema); no glyphs or wikilinks.

## Tests (new `tests/test_compare_charts.py`, plus ephemeris additions)

- Motion helper: applying/separating both directions, retrograde body, wraparound at 0°/360° and
  180°, missing speeds, near-stationary, exact edge.
- Regression fixtures frozen from real 2026-09-19 data (Mars–Neptune quincunx separating;
  Mars–Mercury sextile applying; Saturn–Moon sextile applying while retrograde; Neptune–Saturn
  opposition separating).
- `compare_charts()`: labels, `include_angles` matrix, `planets_only` alias and precedence.
- Formatters: text (byte-identical original lines, appended line, omissions on null); JSON (valid,
  typed numbers, nulls).
- `handle_compare_charts()`: defaults unchanged, invalid enums, unknown event label.
- Ephemeris: `speed` present on planets.

## Docs / release checklist

Docs: `CHANGELOG.md` (`[Unreleased]`), `ARCHITECTURE.md` (#15), `ROADMAP.md`, `AGENTS.md` (test
count), `README.md` (one use case). `DATABASE_SCHEMA.md`: no change.
Release (only on explicit approval): `scripts/bump_version.py 0.13.0`, merge `--no-ff`, tag, push,
wait for PyPI Action, `mcp-publisher publish`.

## Out of scope / follow-ups

- Location parameter for transit-chart angles (limit documented in the tool description).
- Persisting speed for event charts (they report `applying: null`).
- Native MCP structured output / raising the `mcp` SDK floor.
- Cleaning up the two print-script "tests".
- Clarifying that `time` is UT on `get_transits` and `find_house_placements` descriptions.

## Addendum — UT time semantics (found during implementation prep)

`time` is passed to Swiss Ephemeris as UT. A briefing that asks for "09:00" is really asking for
09:00 UT (04:00 CDT). This made clock-time estimates derived from a snapshot look 5 hours later than
they were. Hence `exact_utc` in the data and the `(≈ … UT)` suffix in the text line: consumers
convert to local time explicitly instead of guessing.
