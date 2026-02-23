# Database Schema — w8s-astro-mcp

SQLite database at `~/.w8s-astro-mcp/astro.db`. All tables created by
SQLAlchemy ORM from models in `src/w8s_astro_mcp/models/`.

## Design Principles

- **Normalized for queryability** — separate tables enable complex SQL analysis
- **Calculation metadata** — track ephemeris version and method for reproducibility
- **Historical accuracy** — denormalized location snapshots preserve transit context
- **Multi-house system support** — charts calculated with any supported system
- **Profile-owned locations** — all locations belong to a profile; no shared/global concept
- **Lazy chart caching** — connection charts calculated on demand, cached with validity flag

---

## Full Entity Relationship Diagram

```mermaid
erDiagram
    app_settings {
        int id PK
        int current_profile_id FK
    }
    house_systems {
        int id PK
        string code
        string name
        bool is_default
    }
    locations {
        int id PK
        int profile_id FK
        string label
        float latitude
        float longitude
        string timezone
        bool is_current_home
    }
    profiles {
        int id PK
        string name
        string birth_date
        string birth_time
        int birth_location_id FK
        int preferred_house_system_id FK
    }
    natal_planets {
        int id PK
        int profile_id FK
        string planet
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
        int house_number
        bool is_retrograde
    }
    natal_houses {
        int id PK
        int profile_id FK
        int house_number
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
        int house_system_id FK
    }
    natal_points {
        int id PK
        int profile_id FK
        string point_type
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
        int house_system_id FK
    }
    transit_lookups {
        int id PK
        int profile_id FK
        int location_id FK
        int house_system_id FK
        datetime lookup_datetime
        string location_snapshot_label
        float location_snapshot_latitude
        float location_snapshot_longitude
        string location_snapshot_timezone
    }
    transit_planets {
        int id PK
        int lookup_id FK
        string planet
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
        int house_number
    }
    transit_houses {
        int id PK
        int lookup_id FK
        int house_number
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    transit_points {
        int id PK
        int lookup_id FK
        string point_type
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    connections {
        int id PK
        string label
        string type
        string start_date
    }
    connection_members {
        int id PK
        int connection_id FK
        int profile_id FK
    }
    connection_charts {
        int id PK
        int connection_id FK
        string chart_type
        bool is_valid
        string davison_date
        string davison_time
        float davison_latitude
        float davison_longitude
        string davison_timezone
    }
    connection_planets {
        int id PK
        int chart_id FK
        string planet
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    connection_houses {
        int id PK
        int chart_id FK
        int house_number
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    connection_points {
        int id PK
        int chart_id FK
        string point_type
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }

    app_settings ||--o| profiles : "current_profile_id (SET NULL)"
    profiles ||--|| locations : "birth_location_id (RESTRICT)"
    profiles ||--|| house_systems : "preferred_house_system_id (RESTRICT)"
    locations }o--|| profiles : "profile_id (CASCADE)"
    natal_planets }o--|| profiles : "profile_id (CASCADE)"
    natal_houses }o--|| profiles : "profile_id (CASCADE)"
    natal_houses }o--|| house_systems : "house_system_id (RESTRICT)"
    natal_points }o--|| profiles : "profile_id (CASCADE)"
    natal_points }o--o| house_systems : "house_system_id nullable"
    transit_lookups }o--|| profiles : "profile_id (CASCADE)"
    transit_lookups }o--|| locations : "location_id (RESTRICT)"
    transit_lookups }o--|| house_systems : "house_system_id (RESTRICT)"
    transit_planets }o--|| transit_lookups : "lookup_id (CASCADE)"
    transit_houses }o--|| transit_lookups : "lookup_id (CASCADE)"
    transit_points }o--|| transit_lookups : "lookup_id (CASCADE)"
    connection_members }o--|| connections : "connection_id (CASCADE)"
    connection_members }o--|| profiles : "profile_id (RESTRICT)"
    connection_charts }o--|| connections : "connection_id (CASCADE)"
    connection_planets }o--|| connection_charts : "chart_id (CASCADE)"
    connection_houses }o--|| connection_charts : "chart_id (CASCADE)"
    connection_points }o--|| connection_charts : "chart_id (CASCADE)"
```

---

## Domain Diagrams

### Core: Profiles, Locations, Settings

```mermaid
erDiagram
    app_settings {
        int id PK "always 1 — single row"
        int current_profile_id FK "nullable — SET NULL on delete"
    }
    house_systems {
        int id PK
        string code "swetest flag: P W K R C E A"
        string name
        string description
        bool is_default "Placidus = true"
    }
    locations {
        int id PK
        int profile_id FK "nullable during creation only"
        string label "unique per profile"
        float latitude
        float longitude
        string timezone "IANA e.g. America/Chicago"
        bool is_current_home "one true per profile"
    }
    profiles {
        int id PK
        string name
        string birth_date "YYYY-MM-DD — immutable"
        string birth_time "HH:MM — immutable"
        int birth_location_id FK
        int preferred_house_system_id FK
    }

    app_settings ||--o| profiles : "tracks active user"
    profiles ||--|| locations : "birth location"
    profiles ||--|| house_systems : "preferred system"
    locations }o--|| profiles : "owned by"
```

### Natal Charts

```mermaid
erDiagram
    profiles {
        int id PK
        string name
    }
    house_systems {
        int id PK
        string code
        string name
    }
    natal_planets {
        int id PK
        int profile_id FK
        string planet "Sun Moon Mercury Venus ..."
        int degree "0-29 within sign"
        int minutes "0-59"
        float seconds "0-59.999"
        string sign
        float absolute_position "0-359.999 for aspect math"
        int house_number "1-12 nullable"
        bool is_retrograde
        string calculation_method
        string ephemeris_version
    }
    natal_houses {
        int id PK
        int profile_id FK
        int house_system_id FK
        int house_number "1-12"
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    natal_points {
        int id PK
        int profile_id FK
        int house_system_id FK "nullable for nodes"
        string point_type "ASC MC NorthNode Vertex ..."
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }

    natal_planets }o--|| profiles : "profile_id (CASCADE)"
    natal_houses }o--|| profiles : "profile_id (CASCADE)"
    natal_houses }o--|| house_systems : "house_system_id"
    natal_points }o--|| profiles : "profile_id (CASCADE)"
    natal_points }o--o| house_systems : "house_system_id nullable"
```

### Transit History

```mermaid
erDiagram
    transit_lookups {
        int id PK
        int profile_id FK
        int location_id FK
        int house_system_id FK
        datetime lookup_datetime "the moment being analyzed"
        string location_snapshot_label "denormalized for history"
        float location_snapshot_latitude
        float location_snapshot_longitude
        string location_snapshot_timezone
        datetime calculated_at "when the request ran"
    }
    transit_planets {
        int id PK
        int lookup_id FK
        string planet
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
        int house_number "which NATAL house transiting planet is in"
    }
    transit_houses {
        int id PK
        int lookup_id FK
        int house_number
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    transit_points {
        int id PK
        int lookup_id FK
        string point_type
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }

    transit_lookups }o--|| transit_planets : "one lookup, many planets"
    transit_lookups }o--|| transit_houses : "one lookup, 12 houses"
    transit_lookups }o--|| transit_points : "one lookup, many points"
```

### Connections (Phase 7)

```mermaid
erDiagram
    connections {
        int id PK
        string label "e.g. Todd and Sarah"
        string type "romantic family professional friendship"
        string start_date "YYYY-MM-DD optional"
    }
    connection_members {
        int id PK
        int connection_id FK "CASCADE"
        int profile_id FK "RESTRICT — remove from connection first"
    }
    connection_charts {
        int id PK
        int connection_id FK "CASCADE"
        string chart_type "composite or davison"
        bool is_valid "false = stale, needs recalc"
        string davison_date "null for composite"
        string davison_time "null for composite"
        float davison_latitude "null for composite"
        float davison_longitude "null for composite"
        string davison_timezone "null for composite"
        string calculation_method
        string ephemeris_version
    }
    connection_planets {
        int id PK
        int chart_id FK "CASCADE"
        string planet
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    connection_houses {
        int id PK
        int chart_id FK "CASCADE"
        int house_number
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }
    connection_points {
        int id PK
        int chart_id FK "CASCADE"
        string point_type
        int degree
        int minutes
        float seconds
        string sign
        float absolute_position
    }

    connections ||--|{ connection_members : "has members"
    connections ||--|{ connection_charts : "has charts"
    connection_charts ||--|{ connection_planets : "chart_id (CASCADE)"
    connection_charts ||--|{ connection_houses : "chart_id (CASCADE)"
    connection_charts ||--|{ connection_points : "chart_id (CASCADE)"
```

---

## Connection Chart Lifecycle

The `connection_charts.is_valid` flag drives the cache. This state diagram
shows the full lifecycle of a chart from creation through invalidation and
recalculation.

```mermaid
stateDiagram-v2
    [*] --> Uncached : connection created\nor member added

    Uncached --> Valid : get_connection_chart called\n(calculates + saves)

    Valid --> Invalid : member added or removed\n(invalidate_connection_charts)

    Invalid --> Valid : get_connection_chart called\n(recalculates + upserts)

    Valid --> [*] : connection deleted\n(CASCADE removes chart)
    Invalid --> [*] : connection deleted\n(CASCADE removes chart)
```

---

## Key Constraints & Business Rules

**Uniqueness:**
- One natal planet per planet per profile — `UNIQUE(profile_id, planet)`
- One composite and one Davison chart per connection — `UNIQUE(connection_id, chart_type)`
- One membership per person per connection — `UNIQUE(connection_id, profile_id)`
- One location label per profile — `UNIQUE(profile_id, label)`
- One transit lookup per profile/datetime/location/house system combination

**Cascade behavior:**
- Deleting a profile → cascades to natal chart, transit lookups, locations, connection memberships
- Deleting a connection → cascades to members, charts, and all chart positions
- Deleting a connection chart → cascades to all its planets/houses/points

**Restrict behavior:**
- Cannot delete a profile that is a member of a connection (remove them first)
- Cannot delete a location that has transit lookups referencing it
- Cannot delete a house system that is in use

**Position format:** All positions stored as `degree` (int, 0-29), `minutes` (int, 0-59), `seconds` (float, 0-59.999) within sign, plus `absolute_position` (float, 0-359.999°) for aspect math. The `_normalize_position()` method in `DatabaseHelper` coerces swetest decimal-degree output into this format before any write.

---

## Example Queries

```sql
-- Which planets do I check most often in transits?
SELECT tp.planet, COUNT(*) as checks
FROM transit_planets tp
GROUP BY tp.planet
ORDER BY checks DESC;

-- Transits when Moon was in 7th natal house
SELECT tl.lookup_datetime, tp.sign, tp.degree
FROM transit_lookups tl
JOIN transit_planets tp ON tp.lookup_id = tl.id
WHERE tp.planet = 'Moon' AND tp.house_number = 7
ORDER BY tl.lookup_datetime DESC;

-- All fire sign Suns across profiles
SELECT p.name, np.sign, np.degree
FROM profiles p
JOIN natal_planets np ON np.profile_id = p.id
WHERE np.planet = 'Sun'
  AND np.sign IN ('Aries', 'Leo', 'Sagittarius');

-- All connections a profile belongs to
SELECT c.label, c.type
FROM connections c
JOIN connection_members cm ON cm.connection_id = c.id
WHERE cm.profile_id = 1;

-- Stale connection charts needing recalculation
SELECT c.label, cc.chart_type
FROM connections c
JOIN connection_charts cc ON cc.connection_id = c.id
WHERE cc.is_valid = 0;
```

---

## Future Expansion

### `aspects` (not yet implemented)
Precomputed aspects between planet pairs, enabling queries like
"show me all Saturn squares to natal Sun."

Fields would include: profile/lookup FK, planet pair, aspect type
(conjunction/trine/square/etc.), orb, applying/separating flag, and
aspect category (natal-natal, transit-natal, transit-transit).

### `progressions` and `returns` (not yet implemented)
Secondary progressions, solar arcs, solar returns, lunar returns.
Would follow the same planet/house/point child-table pattern as
natal and transit tables.
