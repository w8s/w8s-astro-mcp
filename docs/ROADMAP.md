# w8s-astro-mcp Roadmap

## Future Enhancements

### Database Management & Self-Healing Tools

**Context:**
As the MCP matures and schema evolves, users' existing databases may become incompatible with new code versions. Currently requires manual SQL fixes or re-running migrations.

**Proposed Self-Healing Tools:**

#### 1. `diagnose_database` MCP Tool
```python
"""Check database health and identify issues.

Returns diagnostic information about:
- Schema version (current vs expected)
- Missing tables or columns
- Data integrity issues
- Suggested fixes

Use this when database errors occur or after updates.
Returns: JSON with status and recommended actions
"""
```

**Features:**
- Compare actual schema vs expected schema
- Detect missing tables (like app_settings after upgrade)
- Check for orphaned foreign keys
- Validate data consistency
- Suggest specific fixes

#### 2. `repair_database` MCP Tool
```python
"""Repair database by adding missing tables/columns.

Safely adds missing schema elements without modifying existing data.
Use after schema updates or when diagnose_database reports issues.

Safe to run multiple times - only adds what's missing.
Returns: List of changes made
"""
```

**Features:**
- Add missing tables (e.g., app_settings)
- Add missing columns with sensible defaults
- Create missing indexes
- Update schema_version in app_settings
- Dry-run mode for safety

#### 3. Schema Versioning
Add to AppSettings model:
```python
class AppSettings(Base):
    schema_version: Mapped[int] = mapped_column(default=1)
```

**Migration strategy:**
- v1 → v2: Add app_settings table (done manually 2026-02-12)
- v2 → v3: Future migrations
- Tools detect version and apply upgrades automatically

#### 4. `migrate_database` MCP Tool
```python
"""Upgrade database schema to latest version.

Detects current schema version and applies migrations sequentially.
Backs up database before making changes.

Safe to run - will skip already-applied migrations.
Returns: Migration log showing applied changes
"""
```

**Features:**
- Automatic schema version detection
- Sequential migration application
- Automatic backup before changes
- Rollback capability on failure
- Migration history logging

### Implementation Priority

**Phase 1: Diagnostics (Low-hanging fruit)**
- Add schema_version to AppSettings
- Implement diagnose_database tool
- Document common issues + fixes

**Phase 2: Self-Repair (Medium effort)**
- Implement repair_database tool
- Add dry-run mode
- Test on common schema drift scenarios

**Phase 3: Automated Migration (High effort)**
- Design migration file format
- Implement migrate_database tool
- Create backup/rollback system
- Write migration authoring guide

### Benefits

**For Users:**
- Less downtime when updating MCP
- Clear error messages with solutions
- Self-service fixes via AI agents

**For Developers:**
- Easier schema evolution
- Reduced support burden
- Better testing of upgrade paths

**For AI Agents:**
- Can self-diagnose issues
- Can auto-fix common problems
- Better error recovery

### Notes

**Historical Context:**
- 2026-02-12: Added app_settings table via manual SQL
- Issue: Existing databases created before app_settings didn't have the table
- Fixed manually, but highlighted need for self-healing tools

**Design Principles:**
- Tools should be safe to run multiple times (idempotent)
- Always prefer non-destructive operations
- Provide clear feedback about what changed
- Allow dry-run mode for verification
- Good docstrings so AI agents know when to use them

---

## Multi-Profile Features (Next Major Feature)

### Phase 1: Profile Management
- `create_profile(name, birth_data, location)` - Create friend/family profiles
- `list_profiles()` - Show all profiles
- `set_current_profile(profile_id)` - Switch active user
- `delete_profile(profile_id)` - Remove a profile

### Phase 2: Synastry & Comparison
- `compare_charts(profile1, profile2)` - Relationship analysis
- `get_synastry_aspects(profile1, profile2)` - Inter-chart aspects
- `composite_chart(profile1, profile2)` - Midpoint chart

### Phase 3: Advanced Features
- `family_patterns(profile_ids[])` - Multi-chart analysis
- `transit_alerts(profile_id, conditions)` - Notification system
- `progression_chart(profile_id, date)` - Secondary progressions

---

## Other Future Enhancements

### Data Visualization
- Chart wheel generation (SVG/PNG)
- Transit timeline graphs
- Aspect pattern diagrams

### Integration
- Export charts to standard formats (AstroJSON, etc.)
- Import from other astrology software
- Calendar integration for transit alerts

### Performance
- Cache frequently-accessed transit data
- Optimize natal chart calculations
- Add database indexes for common queries
