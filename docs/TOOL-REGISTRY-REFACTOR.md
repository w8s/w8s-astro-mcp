# Tool registry refactor — plan, status, findings

Working notes for the 0.15.2 refactor. The aim: every tool is one `ToolSpec` (schema, handler,
natal-chart flag) in a registry, so `list_tools`, routing and the data-notice list cannot drift apart
(that drift is what made `setup_owner` unreachable from 0.12.0 to 0.15.0).

## Frozen while refactoring

Tool names, parameters and output. Pinned by `tests/golden/` (tool list, output of every tool that
had no test) and by the `call_tool` tests. Exceptions that may change, each listed under **Changed** in
the CHANGELOG: unified error wording (below).

## Status

| Step | State |
|---|---|
| `registry.py` (`ToolSpec`, `ToolRegistry`, `ToolContext`) | done (#32) |
| Profile, connection, event tools on the registry | done (#32) |
| Transit tools → `tools/transit_tools.py` | done (#33) |
| Tools listed sorted by name; naming note in AGENTS.md | done (#34) |
| Natal chart, compare, house placements, natal image → `tools/chart_tools.py` | done (#35) |
| `call_tool` tests for connection, profile, event tools | done (#36) |
| `visualize_placement_dials` → `chart_tools.py`; `get_profile_info` leaves `server.py` | done |
| System tools (`check_ephemeris`, `download_ephemeris_files`, `view_config`, `setup_astro_config`, `dismiss_data_notice`) → `tools/system_tools.py` | done |
| Delete the `elif` chain and the globals; `ctx` owns db and engine | done |
| Chart-calculation module (`natal_chart`, `local_chart`; `"P"` literals → house-system lookup) | after 0.15.2 |
| Input validation and plain database errors | done (#38) |
| Unified profile-not-found wording; replace the AGENTS.md "Handler Extraction" convention | done |

## 0.15.2 scope

The registry and chart-calculation refactors, plus **unified error wording**: one wording per case for
"profile not found" and friends, and no database internals (SQL, parameters, exception class names) in
any reply. Known leaks, each covered by a strict `xfail` test that must lose its marker when fixed:

- `add_connection_member` for a profile already in the connection (raw `IntegrityError`).
- `add_location` with a label already used by that profile (same).
- `cast_event_chart` with an unknown `profile_id` (chart is shown, then "not saved" with the SQL).
- Not-found messages differ by tool (`Error: Profile 9 not found.`, `Error updating profile: Database
  operation failed: Profile 9 not found`, `Error: Location 99 not found`, ...).

## Input validation gaps (user-visible; candidates for 0.16.0)

Found while writing the profile and event tool tests. Event tools validate their input; profile tools do not.
Each has a strict `xfail` test describing the correct behaviour.

- `create_profile` stores any timezone, birth date, birth time or latitude (`Mars/Base`, `1985-13-45`,
  `25:99`, `123`). The chart for such a profile fails later.
- `update_profile` accepts any text as a birth date or time (`nope`), and the profile keeps it.
- `add_location` stores any timezone name.
- `find_electional_windows` ignores an unknown criterion, so a typo reads as "No candidates found".

## Release buckets

0.15.1 `setup_owner` fix (released) · 0.15.2 registry + chart calculation + unified error wording ·
0.16.0 anything else user-visible: input validation, house-system option, removing the deprecated
`setup_astro_config`, the tool-name verb cleanup (old names kept as aliases), new tools.

## Deferred

Moving the ingress scan and `_normalize_position` out of `DatabaseHelper`; a `black` policy (revisit
after the refactor); a house-system enum (when a user-facing option exists); known-answer tests for the
chart maths against a reference ephemeris (check what `test_ephemeris.py` and `test_real_world_logic.py`
already cover first).

## Test approach

Tests go through `call_tool`, with nothing of ours mocked: expected values are literals or come from an
independent route (a second tool, date arithmetic, a well-known astronomical fact), never from the code
under test. Golden files pin behaviour for the refactor; they do not prove the astrology is right.
`tests/conftest.py` provides the `tool` fixture; `tests/tool_harness.py` the golden helper.
