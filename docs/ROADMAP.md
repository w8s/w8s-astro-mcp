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
- [x] Applying vs separating
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
- [x] 302 tests (model, math, integration)

## Phase 8: Event Charts — Not Started

Standalone charts cast for a moment in time and location — no profile or connection required. Useful for weddings, business launches, electional astrology, and historical event analysis. Compared to natal/connection charts via the existing `compare_charts` tool.

Schema TBD — design separately.

## Phase 9: Database Self-Healing — Not Started

Tools for schema diagnosis and repair as the schema evolves across versions. Motivated by a 2026-02-12 incident where `app_settings` was missing from databases created before that migration.

Planned tools: `diagnose_database`, `repair_database`, `migrate_database` with dry-run mode, backup/rollback, and schema versioning via `AppSettings.schema_version`.

## Future / Maybe

- [ ] Progressions and solar/lunar returns
- [ ] Aspects table (natal-natal, transit-natal, transit-transit)
- [ ] Transits to composite/Davison charts (partial Phase 7 item)
- [ ] Chart wheel visualizer for composite, Davison, and synastry wheels
- [ ] `visualize_custom_chart(planets, title)` — render any arbitrary positions
- [ ] Electional astrology helpers (selecting auspicious moments — builds on Phase 8 event charts)
- [ ] Voice mode ("What's my transit weather?")
