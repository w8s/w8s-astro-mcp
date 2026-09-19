# w8s-astro-mcp Roadmap

## Phase 1: MVP ✅

- [x] Project structure
- [x] Parse ephemeris output (originally swetest; migrated to pysweph in 0.9.0)
- [x] Basic transit data structure
- [x] Detect mechanical changes (degrees, sign changes, stelliums)
- [x] Rich JSON return format
- [x] Interactive setup wizard for birth data

## Phase 2: Smart Analysis ✅

- [x] Retrograde station detection
- [x] Daily motion calculations
- [x] Speed anomaly detection (unusually slow/fast)
- [x] Named locations system
- [x] Location switching (`get_transits(location="work")`)

## Phase 3: Aspect Engine ✅

- [x] Calculate major aspects (conjunction, opposition, square, trine, sextile)
- [x] Configurable orbs
- [x] Applying vs separating — Phase 3 shipped only a placeholder field (`"applying": None`); actually implemented in v0.13.0
- [x] Aspect patterns (T-squares, Grand Trines, etc.)

## Phase 4: Historical & Predictive ✅

- [x] SQLite database (normalized schema, multi-profile)
- [x] Transit-to-natal aspects
- [x] Auto-log every transit request to history
- [x] `get_transit_history` — query logged transits by date range, planet, sign
- [x] `find_last_transit` — scan logged history for last match (sign, retrograde, house)
- [x] `get_ingresses` — ephemeris-backed sign ingress and station forecast (offset, future/past, extended mode for historical/far-future queries)

## Phase 5: Location Intelligence ✅

- [x] Named locations per profile
- [x] Compare to saved locations
- [x] Inline location geocoding — `get_transits(location="Bangkok, Thailand")` resolves any city name via Nominatim without requiring a saved label
- [x] Accurate IANA timezone lookup via `timezonefinder` — replaces US-only longitude estimate; works correctly for historical queries (Bangkok 1995, etc.)
- [x] Ad-hoc locations used for ephemeris call but not persisted to transit history

## Phase 6: Integration — Superseded

The AI assistant (Claude) already handles cross-tool integration natively — combining tarot and astrology workflows, inserting transit summaries into notes, and setting contextual reminders. No server-side implementation needed.

## Phase 7: Connections (Relationship Charts) ✅

- [x] Multi-profile support (create, switch, manage)
- [x] Connection entity — named group of 2+ profiles
- [x] Composite chart (circular mean of absolute positions via atan2)
- [x] Davison chart (UTC timestamp mean → EphemerisEngine at midpoint lat/lng)
- [x] Timezone-aware Davison midpoint calculation
- [x] Normalized schema — planets/houses/points as queryable rows
- [x] Chart caching with `is_valid` invalidation flag
- [x] 6 MCP tools: `create_connection`, `list_connections`, `add_connection_member`, `remove_connection_member`, `get_connection_chart`, `delete_connection`
- [x] 356 tests (model, math, integration)

## Phase 8: Event Charts & Electional Astrology ✅

Charts cast for a moment in time and place — no profile required. Useful for weddings, business launches, historical event analysis, and electional astrology (finding auspicious moments).

- [x] `cast_event_chart` — cast a chart for any date/time/location; optionally save by label
- [x] `list_event_charts` — list all saved event charts
- [x] `delete_event_chart` — remove a saved event chart
- [x] `find_electional_windows` — scan a time window and return candidate moments scored against criteria (Moon not void, planets direct, benefics angular, etc.)
- [x] `compare_charts` gains `event:<label>` resolver — compare any saved event chart to natal, transits, or another event
- [x] Void-of-course Moon detection — full applying-aspect check (not a heuristic): computes remaining degrees in sign and checks all 5 major aspects against all planets

## v0.12.0: AI UX — Multi-Profile Querying ✅

Cross-cutting improvements to how an AI assistant queries profiles. The key insight: the AI user is always the *operator* — other profiles are objects to query *about*, not personas to switch into.

- [x] `set_current_profile` replaced by `setup_owner` — stable one-time identity, not a session switch
- [x] `AppSettings.current_profile_id` → `owner_profile_id` with migration script
- [x] Optional `profile_id` on all single-profile tools — defaults to owner, enables querying anyone without global state changes
- [x] `compare_charts` gains `chart1_profile_id` / `chart2_profile_id` — unambiguous synastry without profile switching
- [x] `find_house_placements` accepts `connection_id` + `chart_type` — place today's sky in composite or Davison house systems
- [x] `find_house_placements` natal house fix — transit placement now uses the target profile's houses, not always the owner's
- [x] Davison chart formatter fix — sign names were dropped from output
- [x] Handler extraction pattern established — complex handlers live in standalone `handle_*()` functions for direct testability
- [x] 13 new tests for `find_house_placements`; 356 total

## v0.13.0: Transit Reading — Direction, Labels, JSON (in progress)

Makes `compare_charts` usable for day-to-day transit reading. Presentation (arrows, links, which angle hits to show) stays with the caller; the server returns data.

- [x] Planet `speed` (signed degrees/day) kept from the ephemeris alongside `is_retrograde`
- [x] Each aspect reports `applying`, signed `days_to_exact`, and `exact_utc` when a chart carries speeds
- [x] Each body is labelled with the chart it came from (natal / transit / `event:<label>`; profile names for synastry)
- [x] `include_angles` (none | natal | transit | both) alongside the all-or-nothing `planets_only` (kept as an alias)
- [x] `format: json` option; `text` stays the default, original lines unchanged, one line appended per aspect
- [x] `handle_compare_charts()` extracted for testability
- [x] First real test coverage for `compare_charts` (the old analysis "tests" were print scripts); 440 total
- [ ] Release: version bump, merge, tag, PyPI, MCP Registry

## v0.14.0: Local Times Converted to UT (in progress)

Fixes a bug found while building v0.13.0: local birth, event and electional times were handed to the ephemeris as if they were UT.

- [x] `utils/timezones.py` — local -> UT with `zoneinfo` (historical DST), clear errors
- [x] Natal chart calculation, `cast_event_chart` and `find_electional_windows` convert before calculating
- [x] `w8s-astro-recalculate` — dry-run-first recalculation of stored natal and (opt-in) event charts, with backup
- [x] `tzdata` dependency; tool descriptions say which times are local and which are UT
- [x] Server `instructions` (local vs UT times, how to treat a data notice) and a condition-based data notice when stored natal charts predate the fix
- [x] `dismiss_data_notice` tool and a `dismissed_notices` table: the user can dismiss the notice; a different stale chart brings it back
- [ ] Release: version bump, merge, tag, PyPI, MCP Registry; add a warning line to the GitHub release pages of affected older versions (external edit, needs approval)

## Phase 9: Database Self-Healing — In Progress

Tools for schema diagnosis and repair as the schema evolves across versions.

Note: `scripts/migrate_owner_profile.py` (v0.12.0) is the first concrete migration script in this direction — idempotent, SQLite-safe column rename with clear output. Phase 9 will generalize this into a full toolset.

Planned tools: `diagnose_database`, `repair_database`, `migrate_database` with dry-run mode, backup/rollback, and schema versioning via `AppSettings.schema_version`.

## Future / Maybe

- [ ] Progressions and solar/lunar returns
- [ ] Aspects table (natal-natal, transit-natal, transit-transit)
- [ ] Transits to composite/Davison charts (partial Phase 7 item)
- [ ] Chart wheel visualizer for composite, Davison, and synastry wheels
- [ ] `visualize_custom_chart(planets, title)` — render any arbitrary positions
- [ ] Voice mode ("What's my transit weather?")
- [ ] `compare_charts`: a location argument for transit-chart angles (today they use the owner's current home location)
- [ ] Persist planet speed for saved event charts, so event-vs-natal comparisons can report applying/separating
- [ ] Native MCP structured output for `format: json` (would raise the `mcp` SDK floor)
- [ ] A `timezone` argument for the transit tools (`get_transits`, `find_house_placements`, `compare_charts`), so callers can pass local times
- [ ] Optional MCP tool `recalculate_natal_charts` (dry run by default, `confirm: true` to apply) so an assistant can run the fix for users who never find the console command
- [ ] Relocation-chart tool (a birth chart cast for a different place at the birth moment)
- [ ] Turn `tests/test_analysis_tools.py` and `tests/test_real_world_logic.py` from print scripts into real tests
