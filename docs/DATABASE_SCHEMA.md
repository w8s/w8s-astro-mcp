# Database Schema - w8s-astro-mcp

Complete normalized schema for astrological analysis and transit tracking.

## Design Principles

- **Normalized for queryability**: Separate tables enable complex SQL analysis
- **Calculation metadata**: Track ephemeris version and method for reproducibility  
- **Historical accuracy**: Denormalized location snapshots preserve context
- **Multi-house system support**: Can calculate charts with different systems
- **Future-proof**: Ready for aspects, progressions, returns

## Core Tables

### `house_systems` (Reference Data)
Static lookup table for house calculation methods supported by swetest.

**Fields:**
- `id` - Primary key
- `code` - Swetest parameter (P, W, K, R, C, E, A, etc.)
- `name` - Display name (Placidus, Whole Sign, Koch, etc.)
- `description` - Explanation
- `is_default` - Boolean flag

### `profiles`
Identity and birth data for people whose charts we track.

**Fields:**
- `id` - Primary key
- `name` - Person's name
- `birth_date` - YYYY-MM-DD
- `birth_time` - HH:MM (24-hour)
- `birth_location_id` - FK to locations
- `is_primary` - Boolean (user's own chart)
- `preferred_house_system_id` - FK to house_systems
- `created_at`, `updated_at`

**Business Rules:**
- Only one `is_primary=true` per database
- Birth data immutable (would invalidate natal chart)

### `locations`
Reusable location data for convenience and analysis.

**Fields:**
- `id` - Primary key
- `profile_id` - FK to profiles (NULL = shared/global)
- `label` - User-friendly name ("Home", "Office", "Paris Trip")
- `latitude`, `longitude`, `timezone`
- `is_current_home` - Boolean (default for transits)
- `created_at`, `updated_at`

**Business Rules:**
- Unique `(profile_id, label)` constraint
- Only one `is_current_home=true` per profile
- Reserved labels: "current", "birth"

## Natal Chart Tables

Calculated once per profile, cached for reuse.

### `natal_planets`
**Fields:**
- `id`, `profile_id` (FK)
- `planet` - Name (Sun, Moon, Mercury, etc.)
- `degree`, `minutes`, `seconds` - Position within sign (0-29.999°)
- `sign` - Zodiac sign
- `absolute_position` - 0-359.999° (computed for aspect calculations)
- `house_number` - 1-12
- `is_retrograde` - Boolean
- `calculated_at`, `calculation_method`, `ephemeris_version`

### `natal_houses`
**Fields:**
- `id`, `profile_id` (FK)
- `house_number` - 1-12
- `degree`, `minutes`, `seconds`, `sign`, `absolute_position`
- `house_system_id` - FK (which system calculated this)
- `calculated_at`, `calculation_method`, `ephemeris_version`

### `natal_points`
**Fields:**
- `id`, `profile_id` (FK)
- `point_type` - "Ascendant", "MC", "North Node", "Vertex", etc.
- `degree`, `minutes`, `seconds`, `sign`, `absolute_position`
- `house_system_id` - FK (nullable for nodes)
- `calculated_at`, `calculation_method`, `ephemeris_version`

## Transit Tables

### `transit_lookups`
History of user-initiated transit calculations.

**Fields:**
- `id`, `profile_id` (FK)
- `lookup_date`, `lookup_time` - When in time to calculate for
- `location_id` - FK to locations (nullable for one-off lookups)
- `location_snapshot_name`, `location_snapshot_lat/lng/tz` - Denormalized
- `notes` - User annotations
- `created_at` - When lookup was performed

**Why denormalized location?**
Preserves historical accuracy if saved location changes later.

### `transit_planets`, `transit_houses`, `transit_points`
Same structure as natal equivalents, but:
- `lookup_id` FK instead of `profile_id`
- Multiple sets per profile (one per lookup)
- For planets: `house_number` = which NATAL house they're transiting

## Example Queries

### Analysis: Transit patterns
```sql
-- Which planets do I check most often?
SELECT tp.planet, COUNT(*) as checks
FROM transit_planets tp
GROUP BY tp.planet
ORDER BY checks DESC;

-- Transits when Moon was in 7th house
SELECT tl.*, tp.*
FROM transit_lookups tl
JOIN transit_planets tp ON tp.lookup_id = tl.id
WHERE tp.planet = 'Moon' AND tp.house_number = 7;
```

### Analysis: Profile patterns
```sql
-- Find fire sign Suns
SELECT p.name, np.sign
FROM profiles p
JOIN natal_planets np ON np.profile_id = p.id
WHERE np.planet = 'Sun' 
  AND np.sign IN ('Aries', 'Leo', 'Sagittarius');
```

### History tracking
```sql
-- Transit lookup frequency
SELECT DATE(created_at) as day, COUNT(*) as lookups
FROM transit_lookups
WHERE profile_id = 1
GROUP BY day
ORDER BY day DESC;
```

## Future Expansion

### `aspects` (Not Yet Implemented)
- Profile/lookup relationship
- Planet pairs, aspect type, orb, applying/separating
- Categories: natal-natal, transit-natal, transit-transit
- Enables: "Show me all Saturn squares to my Sun"

### `progressions`, `returns` (Not Yet Implemented)
- Secondary progressions, solar arcs
- Solar returns, lunar returns
- Similar structure to natal/transit tables
