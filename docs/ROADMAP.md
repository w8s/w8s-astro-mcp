# w8s-astro-mcp Roadmap

## Phase 1: MVP ✅
- [x] Project structure
- [x] Parse swetest output
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

## Phase 4: Historical & Predictive — Partial
- [x] SQLite database (normalized schema, multi-profile)
- [x] Transit-to-natal aspects
- [x] Auto-log every transit request to history
- [ ] Query historical transits ("last month's transits")
- [ ] "When was the last time...?" queries
- [ ] Future transit lookups ("Next Mercury retrograde?")

## Phase 5: Location Intelligence — Partial
- [x] Named locations per profile
- [x] Compare to saved locations
- [ ] Device location detection (CoreLocationCLI integration)
- [ ] Opt-in auto-detection config
- [ ] Travel mode (temporary location override)
- [ ] Location history log
- [ ] "Ask me when location changes" prompt

## Phase 6: Integration — Not Started
- [ ] Combine with tarot workflow
- [ ] Calendar integration (transit alerts for important meetings)
- [ ] Obsidian daily note auto-insertion
- [ ] Custom alert thresholds

## Phase 7: Connections (Relationship Charts) ✅
- [x] Multi-profile support (create, switch, manage)
- [x] Connection entity — named group of 2+ profiles
- [x] Composite chart (circular mean of absolute positions via atan2)
- [x] Davison chart (UTC timestamp mean → swetest at midpoint lat/lng)
- [x] Timezone-aware Davison midpoint calculation
- [x] Normalized schema — planets/houses/points as queryable rows
- [x] Chart caching with `is_valid` invalidation flag
- [x] 6 MCP tools: `create_connection`, `list_connections`,
  `add_connection_member`, `remove_connection_member`,
  `get_connection_chart`, `delete_connection`
- [x] 236 tests (model, math, integration)
- [ ] Transits to composite/Davison charts

## Phase 8: Event Charts — Not Started

Standalone charts cast for a moment in time and location — no profile or
connection required. Useful for weddings, business launches, electional
astrology, and historical event analysis. Compared to natal/connection
charts via the existing `compare_charts` tool.

Schema TBD — design separately.

## Phase 9: Database Self-Healing — Not Started

Tools for schema diagnosis and repair as the schema evolves across versions.
Motivated by a 2026-02-12 incident where `app_settings` was missing from
databases created before that migration.

Planned tools: `diagnose_database`, `repair_database`, `migrate_database`
with dry-run mode, backup/rollback, and schema versioning via
`AppSettings.schema_version`.

## Future / Maybe
- [ ] Progressions and solar/lunar returns
- [ ] Aspects table (natal-natal, transit-natal, transit-transit)
- [ ] Transits to composite/Davison charts (partial Phase 7 item)
- [ ] Chart wheel visualizer for composite, Davison, and synastry wheels
- [ ] `visualize_custom_chart(planets, title)` — render any arbitrary positions
- [ ] Electional astrology helpers
- [ ] Voice mode ("What's my transit weather?")
