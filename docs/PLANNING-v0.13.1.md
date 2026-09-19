# v0.13.1 Planning — Convert Local Times to UT

**Status:** spec approved 2026-09-19; implementation on `fix/local-time-to-ut`, stacked on
`feature/transit-direction-json` (v0.13.0, unreleased at the time of writing).
**Lifecycle:** delete after release, folding the durable parts into `ARCHITECTURE.md`
(decision #16).

## Problem

Swiss Ephemeris takes UT. Several tools collect a *local* time plus an IANA `timezone` and then pass
the local time to the ephemeris unchanged, so the `timezone` is recorded or displayed but never
applied:

| Where | Local input | What happened |
|---|---|---|
| `get_natal_chart_data` (natal charts, the only place they are calculated; lazy) | `Profile.birth_time` + birth `Location.timezone` | birth time treated as UT |
| `cast_event_chart` | `time` + `timezone` | event time treated as UT |
| `find_electional_windows` | `start_date`/`end_date` + `timezone` | scan times treated as UT and shown as local |

Impact: wrong Ascendant, MC and houses for every profile, and a wrong Moon (and slightly wrong
Mercury/Venus/Mars) — verified against an independent chart site. Davison charts already convert
correctly. Transit tools (`get_transits`, `find_house_placements`, `get_ingresses`,
`compare_charts`) take UT by design and have no timezone input; they are unchanged.

## Behavior

1. **`utils/timezones.py`** — `local_to_utc(date, time, tz)` using `zoneinfo` (so historical DST
   rules apply) returning a UTC datetime; `TimezoneError` for bad input. Ambiguous local times
   (DST fall-back) take the first occurrence; nonexistent ones (spring-forward gap) shift forward.
2. **Natal** — convert at the single calculation site using the birth location's timezone. The
   stored profile stays local, so `birth_time` keeps meaning what a birth record says.
3. **Events** — `cast_event_chart` converts before casting. Existing output lines are unchanged; one
   `**UT:**` line is appended. Stored `event_time` / `timezone` stay local.
4. **Electional** — `start_date`/`end_date` are local dates in `timezone`; the scan steps in UT
   (real elapsed minutes, DST-safe) and prints local times.
5. **Recalculation tool** — `w8s-astro-recalculate` (console script; module
   `w8s_astro_mcp.recalculate_natal`). Explicit selection required (`--all` or `--profile-id N`),
   dry run unless `--apply`, database backup before writing, connection charts invalidated,
   before/after report, 12:00 placeholder times flagged, `--events` opts in to saved event charts.
   Idempotent: it recalculates from the stored local birth data, so a second run changes nothing.
6. **Dependency** — `tzdata` (Windows and minimal containers have no system tz database).
7. **Descriptions and docs** say what is local and what is UT.

## Defaults confirmed

- Separate patch release (0.13.1), stacked on the v0.13.0 branch.
- Old stored charts are fixed by the recalculation tool only (no automatic recalculation).
- Saved event charts are opt-in (`--events`); the four "*-vegas-march2026" charts hold birth clock
  times labelled as LA time, so recalculating them would not make them relocation charts.
- `tzdata` is an unconditional dependency.

## Changes from the first sketch

- The recalculation tool is a console command plus a module rather than `scripts/*.py`, because
  `uvx` and `pip` users have no `scripts/` directory.

## Tests

Conversion cases (three real zones/dates, date rollover both ways, DST gap and fold, half-hour
zone, bad input); natal calculation end to end against a temporary database; `cast_event_chart`
and `find_electional_windows` passing UT to the engine; the recalculation tool (dry run writes
nothing, apply fixes a wrongly-stored chart, idempotent, selection required, other profiles
untouched, events opt-in).

## Out of scope

Timezone argument for transit tools; automatic detection of stale charts; relocation-chart tooling.
