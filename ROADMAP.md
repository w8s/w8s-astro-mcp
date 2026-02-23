# w8s-astro-mcp Development Roadmap

## Phase 1: MVP ✅ (In Progress)
- [x] Project structure created
- [x] Parse swetest output
- [x] JSON cache (7-day rolling)
- [x] Basic transit data structure
- [x] Detect mechanical changes (degrees, sign changes, stelliums)
- [x] Rich JSON return format
- [x] Setup wizard for birth data config
- [x] Generate markdown tables

## Phase 2: Smart Analysis
- [x] Retrograde station detection
- [x] Daily motion calculations
- [x] Speed anomaly detection (unusually slow/fast)
- [x] Named locations system
- [x] Location switching (`get_transits(location="work")`)

## Phase 3: Aspect Engine
- [x] Calculate major aspects (conjunction, opposition, square, trine, sextile)
- [x] Configurable orbs
- [x] Applying vs separating
- [x] Aspect patterns (T-squares, Grand Trines, etc.)

## Phase 4: Historical & Predictive
- [x] SQLite migration for long-term storage
- [ ] Query historical transits
- [ ] "When was the last time...?" queries
- [ ] Future transit lookups ("Next Mercury retrograde?")
- [x] Transit-to-natal aspects

## Phase 5: Location Intelligence 🎯
- [ ] **Device location detection** (CoreLocationCLI integration)
- [ ] Opt-in auto-detection config
- [x] Compare to saved locations ("You're at home" vs "You're traveling")
- [ ] Travel mode (temporary location override)
- [ ] Location history log
- [ ] "Ask me when location changes" prompt

## Phase 6: Integration
- [ ] Combine with tarot workflow
- [ ] Calendar integration (transit alerts for important meetings)
- [ ] Obsidian daily note auto-insertion
- [ ] Custom alert thresholds

## Phase 7: Connections (Relationship Charts)

### Overview
A `connection` is any grouping of 2+ profiles for astrological comparison. Supports
romantic, family, professional, and friendship dynamics. Composite and Davison charts
are calculated from member profiles and stored as normalized rows (not JSON blobs),
following the same pattern as natal_planets/natal_houses/natal_points.

### Key Design Decisions

**Connections support N members (not just pairs)**
The junction table handles any number of members. Composite chart math scales cleanly
to N people (average of absolute positions). Davison math also scales to N (arithmetic
mean of birth datetimes and locations) — historically rare for 3+ people only because
manual calculation was prohibitive, not because it's invalid. Leave interpretation to
the astrologer.

**Locations are 1 entity : N locations, not shared across entities**
Each profile owns its own locations. No global location deduplication. If two profiles
share a physical address, it is entered separately for each. If a location changes,
the querent or astrologer should probe for new info. Simple, clean, no polymorphic FK.

**Stored charts, not recalculated on demand**
Composite and Davison planet positions are stored after first calculation.
Invalidation strategy: `is_valid = FALSE` flag on `connection_charts` when any member
profile's birth data changes. Recalculate on next access. Consistent with existing
natal chart cache invalidation pattern (application layer, not SQLite triggers).

**Normalized rows, not JSON blobs**
Planet/house/point data follows the exact same structure as natal_planets, natal_houses,
natal_points — degree, minutes, seconds, sign, absolute_position, calculated_at,
calculation_method, ephemeris_version. Queryable, consistent, auditable.

**Event charts are independent (Phase 8)**
Event charts (weddings, business launches, electional candidates) belong to no profile
or connection. They are standalone entities cast for a moment in time and location.
Comparison to natal/connection charts is done via the existing compare_charts tool.
See Phase 8.

**SQL constraints for structural integrity, application layer for behavioral logic**
- SQL: FK cascades, unique constraints, referential integrity
- Application: invalidation on birth data change, minimum member count (≥2), chart
  type validation

### Schema

```sql
-- The connection entity
CREATE TABLE connections (
  id INTEGER PRIMARY KEY,
  label VARCHAR(200) NOT NULL,
  type VARCHAR(50),              -- romantic/family/professional/friendship
  start_date VARCHAR(10),        -- optional, ISO date
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);

-- Members junction — a person appears once per connection
CREATE TABLE connection_members (
  id INTEGER PRIMARY KEY,
  connection_id INTEGER NOT NULL,
  profile_id INTEGER NOT NULL,
  UNIQUE (connection_id, profile_id),
  FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE CASCADE,
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE RESTRICT
);

-- One row per chart type per connection
CREATE TABLE connection_charts (
  id INTEGER PRIMARY KEY,
  connection_id INTEGER NOT NULL,
  chart_type VARCHAR(20) NOT NULL,   -- composite / davison
  -- Davison-specific: stores the calculated midpoint moment and location
  davison_date VARCHAR(10),
  davison_time VARCHAR(5),
  davison_latitude FLOAT,
  davison_longitude FLOAT,
  davison_timezone VARCHAR(50),
  is_valid BOOLEAN NOT NULL DEFAULT 1,
  calculated_at DATETIME,
  calculation_method VARCHAR(50),
  ephemeris_version VARCHAR(20),
  UNIQUE (connection_id, chart_type),
  FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE CASCADE
);

-- Normalized planet rows — mirrors natal_planets exactly
CREATE TABLE connection_planets (
  id INTEGER PRIMARY KEY,
  connection_chart_id INTEGER NOT NULL,
  planet VARCHAR(20) NOT NULL,
  degree INTEGER NOT NULL,
  minutes INTEGER NOT NULL,
  seconds FLOAT NOT NULL,
  sign VARCHAR(20) NOT NULL,
  absolute_position FLOAT NOT NULL,
  house_number INTEGER,
  is_retrograde BOOLEAN NOT NULL,
  calculated_at DATETIME NOT NULL,
  calculation_method VARCHAR(50) NOT NULL,
  ephemeris_version VARCHAR(20),
  UNIQUE (connection_chart_id, planet),
  FOREIGN KEY (connection_chart_id) REFERENCES connection_charts(id) ON DELETE CASCADE
);

-- Houses — mirrors natal_houses
CREATE TABLE connection_houses (
  id INTEGER PRIMARY KEY,
  connection_chart_id INTEGER NOT NULL,
  house_system_id INTEGER NOT NULL,
  house_number INTEGER NOT NULL,
  degree INTEGER NOT NULL,
  minutes INTEGER NOT NULL,
  seconds FLOAT NOT NULL,
  sign VARCHAR(20) NOT NULL,
  absolute_position FLOAT NOT NULL,
  calculated_at DATETIME NOT NULL,
  calculation_method VARCHAR(50) NOT NULL,
  ephemeris_version VARCHAR(20),
  UNIQUE (connection_chart_id, house_number),
  FOREIGN KEY (connection_chart_id) REFERENCES connection_charts(id) ON DELETE CASCADE,
  FOREIGN KEY (house_system_id) REFERENCES house_systems(id) ON DELETE RESTRICT
);

-- Points (ASC, MC) — mirrors natal_points
CREATE TABLE connection_points (
  id INTEGER PRIMARY KEY,
  connection_chart_id INTEGER NOT NULL,
  house_system_id INTEGER NOT NULL,
  point_type VARCHAR(20) NOT NULL,
  degree INTEGER NOT NULL,
  minutes INTEGER NOT NULL,
  seconds FLOAT NOT NULL,
  sign VARCHAR(20) NOT NULL,
  absolute_position FLOAT NOT NULL,
  calculated_at DATETIME NOT NULL,
  calculation_method VARCHAR(50) NOT NULL,
  ephemeris_version VARCHAR(20),
  UNIQUE (connection_chart_id, point_type),
  FOREIGN KEY (connection_chart_id) REFERENCES connection_charts(id) ON DELETE CASCADE,
  FOREIGN KEY (house_system_id) REFERENCES house_systems(id) ON DELETE RESTRICT
);
```

### Chart Comparison Matrix
```
natal      vs natal       → synastry (compare_charts, already works)
natal      vs transits    → personal forecast (already works)
natal      vs event       → electional / event analysis (Phase 8)
composite  vs transits    → relationship forecast
composite  vs event       → how does this event affect the relationship?
davison    vs transits    → relationship forecast (alternate method)
event      vs event       → how do two moments relate? (rare but valid)
```

### MCP Tools Needed
- `create_connection(label, type, profile_ids[])` 
- `get_connection_chart(connection_id, chart_type)` — calculates + caches
- `list_connections()`
- `add_connection_member(connection_id, profile_id)`
- `remove_connection_member(connection_id, profile_id)` — invalidates charts
- `get_transits_to_connection(connection_id, chart_type, date, location)`

## Phase 8: Event Charts

Event charts are standalone — no profile or connection required. Cast for a moment
in time and location. Useful for:
- Wedding / partnership inception charts
- Business launch charts
- Electional astrology (finding an optimal future moment)
- Historical event analysis

Compared to natal/connection charts via existing `compare_charts` tool.

Schema TBD — design separately.

## Phase 9: Database Self-Healing & Migration

As the schema evolves, users' existing databases may become incompatible with new
code versions. These tools allow self-diagnosis and repair without manual SQL intervention.

**Historical context:** 2026-02-12 — `app_settings` table was missing from databases
created before that migration, requiring a manual fix. This phase prevents recurrence.

### Schema Versioning
Add `schema_version` to `AppSettings` model (integer, default 1). Migrations detect
current version and apply upgrades sequentially.

### MCP Tools

**`diagnose_database`** — Check database health and identify issues.
Compares actual schema vs expected, detects missing tables/columns, checks orphaned
foreign keys, validates data consistency. Returns JSON with status and recommended actions.

**`repair_database`** — Safely add missing tables/columns without modifying existing data.
Idempotent — safe to run multiple times. Creates missing indexes, updates schema_version.
Supports dry-run mode for verification.

**`migrate_database`** — Upgrade schema to latest version sequentially.
Detects current version, applies migrations in order, backs up database before changes,
logs migration history. Rollback capability on failure.

### Implementation Priority
1. Schema versioning + `diagnose_database` (low effort, high value)
2. `repair_database` with dry-run mode
3. `migrate_database` with backup/rollback

### Design Principles
- Idempotent operations — safe to run multiple times
- Non-destructive by default
- Dry-run mode for all write operations
- Clear feedback about what changed
- Good docstrings so AI agents know when to invoke them

## Future/Maybe
- [ ] Progressions & Solar Returns
- [ ] Synastry (relationship charts)
  - [x] Natal comparison & aspect analysis
  - [x] Composite chart (midpoint method)
  - [x] Davison chart (midpoint date/location method)
  - [ ] Transits to composite/Davison charts
  - [ ] **Chart wheel visualizer** — render composite, Davison, natal, and synastry wheels as PNG (custom Python renderer, not MCP-tool-dependent)
  - [ ] **`visualize_custom_chart(planets, title)` tool** — MCP-native version accepting arbitrary planet positions; enables one-call rendering of composite/Davison/synastry wheels without manual calculation
- [ ] Electional astrology helpers
- [ ] Voice mode integration ("What's my transit weather?")
