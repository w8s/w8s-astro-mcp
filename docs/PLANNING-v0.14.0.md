# v0.14.0 Planning — Convert Local Times to UT

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

- Separate patch release (0.14.0), stacked on the v0.13.0 branch.
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

## Addendum — telling users (agreed after the first implementation)

The bug is a breaking change of sorts: results change and users must act. So:

- **Version:** 0.14.0, not 0.13.1 (SemVer, pre-1.0). Release order: 0.13.0 (additive), then 0.14.0.
- **In the product:** server `instructions` (durable local-vs-UT rules) and a condition-based data notice
  (`utils/chart_health.py`) — repeats until the charts are recalculated, needs no stored state.
- **CHANGELOG is the announcement:** the GitHub Release body is built from the version's CHANGELOG section,
  so the plain-language headline, a Breaking section and the fix come first. README gets a banner.
- **After release, with approval:** a warning line on the GitHub release pages of affected older versions.
- **Not included:** an MCP tool to run the recalculation (roadmap), an opt-out for the notice.

## Addendum — dismissing the notice

The user must be able to say "stop reminding me". Decision: a small **new table** (`dismissed_notices`) and a
`dismiss_data_notice` tool (`undo=true` reverses it), not a config file.

- **Why the database:** the project moved from `config.json` to SQLite in v0.9; the stored value is a list of
  profile IDs that only makes sense next to this database; and `create_all` adds a new table to an existing database
  on the next start, so there is no migration (a new column on `app_settings` would have needed one).
- **What is remembered:** the stale profile IDs the user had seen. The notice stays hidden while the stale profiles are
  a subset of those (fixing some does not bring it back); a different stale chart does.
- **What it does not do:** fix anything. The tool says so, and how to recalculate.

## Addendum — one release

Decided after the 0.13.0 branch was ready: there is **no separate 0.13.0 release**. The `compare_charts` work
(previously planned as 0.13.0) ships inside 0.14.0 with the local-time fix, so nobody receives it without the fix,
the data notice and the recalculation tool, and there is one release cycle instead of two. The CHANGELOG folds the
0.13.0 entries into the 0.14.0 entry; both planning docs are deleted in the release commit.
