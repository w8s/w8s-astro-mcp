# Profile Management Tools - Implementation Plan

**Branch:** `feature/profile-management-tools`  
**Created:** 2026-02-12  
**Status:** Stubbed out, ready for implementation

## Overview

Add MCP tools for creating, updating, and managing astrological profiles. Enables multi-profile support for friends, family, synastry analysis, etc.

## Files Created/Modified

**New files:**
- `src/w8s_astro_mcp/tools/profile_management.py` - Tool definitions and handlers

**Modified files:**
- `src/w8s_astro_mcp/server.py` - Import and integrate profile tools

## Stubbed Tools (7 total)

### 1. `list_profiles`
**Purpose:** Show all profiles with ID, name, birth date, and current indicator  
**Schema:** No parameters  
**Returns:** Formatted list of all profiles

**Implementation checklist:**
- [ ] Query all profiles from database
- [ ] Get current_profile_id from AppSettings
- [ ] Format with (*) indicator for current profile
- [ ] Handle empty profile list

### 2. `create_profile`
**Purpose:** Create new profile for friends, family, synastry  
**Schema:**
```json
{
  "name": "string",
  "birth_date": "YYYY-MM-DD",
  "birth_time": "HH:MM",
  "birth_location_name": "string",
  "birth_latitude": "number",
  "birth_longitude": "number",
  "birth_timezone": "string"
}
```

**Implementation checklist:**
- [ ] Create Location for birth place
- [ ] Create Profile linked to Location
- [ ] Ask user if this should be current profile
- [ ] If yes, call set_current_profile
- [ ] Return profile ID and confirmation

### 3. `update_profile`
**Purpose:** Update profile fields (name, birth_date, birth_time)  
**Schema:**
```json
{
  "profile_id": "integer",
  "field": "name|birth_date|birth_time",
  "value": "string"
}
```

**Implementation checklist:**
- [ ] Validate profile exists
- [ ] Validate field name (enum check)
- [ ] Update field in database
- [ ] If birth_date/birth_time changed, invalidate natal cache
  - [ ] Delete natal_planets rows
  - [ ] Delete natal_houses rows
  - [ ] Delete natal_points rows
- [ ] Return confirmation

**Natal cache invalidation logic:**
```python
if field in ["birth_date", "birth_time"]:
    # Delete cached natal data
    session.query(NatalPlanet).filter_by(profile_id=profile_id).delete()
    session.query(NatalHouse).filter_by(profile_id=profile_id).delete()
    session.query(NatalPoint).filter_by(profile_id=profile_id).delete()
```

### 4. `delete_profile`
**Purpose:** Delete profile and all associated data  
**Schema:**
```json
{
  "profile_id": "integer",
  "confirm": "boolean" (must be true)
}
```

**Implementation checklist:**
- [ ] Check confirm=true
- [ ] Validate profile exists
- [ ] Delete profile (CASCADE handles natal data)
- [ ] If was current_profile, AppSettings sets to NULL automatically (ON DELETE SET NULL)
- [ ] Return confirmation

**Database CASCADE behavior:**
- Deleting Profile auto-deletes:
  - natal_planets (FK: profile_id)
  - natal_houses (FK: profile_id)
  - natal_points (FK: profile_id)
  - transit_lookups (FK: profile_id)

### 5. `set_current_profile`
**Purpose:** Switch active profile  
**Schema:**
```json
{
  "profile_id": "integer"
}
```

**Implementation checklist:**
- [ ] Use existing db_helper.set_current_profile(profile_id)
- [ ] Validate profile exists
- [ ] Update AppSettings.current_profile_id
- [ ] Return confirmation with profile name

### 6. `add_location`
**Purpose:** Add saved location (home, office, travel, etc.) for a profile  
**Schema:**
```json
{
  "profile_id": "integer" (required),
  "label": "string",
  "latitude": "number",
  "longitude": "number",
  "timezone": "string",
  "set_as_home": "boolean" (optional)
}
```

**Implementation checklist:**
- [ ] Validate profile exists
- [ ] Create Location with profile_id
- [ ] If set_as_home=true:
  - [ ] Unset is_current_home on other locations for this profile
  - [ ] Set is_current_home=true on new location
- [ ] Return location ID and confirmation

**Note:** All locations must belong to a profile (profile_id required)

### 7. `remove_location`
**Purpose:** Delete saved location  
**Schema:**
```json
{
  "location_id": "integer"
}
```

**Implementation checklist:**
- [ ] Validate location exists
- [ ] Check not used as birth_location (FK constraint)
  - [ ] Query profiles where birth_location_id=location_id
  - [ ] If found, error: "Cannot delete - used as birth location"
- [ ] Delete location
- [ ] Return confirmation

## Implementation Order

**Phase 1: Read-only (easiest):**
1. list_profiles
2. set_current_profile (uses existing db_helper method)

**Phase 2: Basic creation:**
3. create_profile
4. add_location

**Phase 3: Modifications:**
5. update_profile (needs natal cache invalidation)
6. remove_location (needs FK validation)
7. delete_profile (uses CASCADE)

## Testing Strategy

**Unit tests (create `tests/test_profile_management.py`):**
- Test each tool handler independently
- Mock database session
- Test error cases (profile not found, etc.)

**Integration tests:**
- Create profile → set as current → verify get_natal_chart uses it
- Update profile → verify natal cache invalidated
- Delete profile → verify CASCADE deletes natal data
- Delete current profile → verify AppSettings.current_profile_id = NULL

**Manual testing:**
- Restart MCP server after implementation
- Use tools through Claude interface
- Verify multi-profile workflow:
  1. list_profiles
  2. create_profile (friend)
  3. set_current_profile (friend)
  4. get_natal_chart (should show friend's chart)
  5. set_current_profile (back to you)

## Edge Cases to Handle

**create_profile:**
- Duplicate names allowed (profiles distinguished by ID)
- Birth location can be same as existing location (create new Location)

**update_profile:**
- Prevent updating birth_location_id directly (not in allowed fields)
- Changing birth data invalidates cached chart
- Name can be changed to anything (including duplicates)

**delete_profile:**
- Cannot delete if it's the only profile? (Decision: allow it, current_profile_id → NULL)
- Deleting current profile is safe (AppSettings ON DELETE SET NULL)

**set_current_profile:**
- Setting NULL? (Decision: could add this for "no active profile")
- Invalid profile_id? (Error: profile not found)

**add_location:**
- Duplicate labels allowed (locations distinguished by ID)
- Multiple "Home" locations? (Yes, use is_current_home flag)

**remove_location:**
- Location used as birth_location → FK constraint error
- Location used as current_home → allowed (just clear the flag)

## Database Helpers Needed

**Already exist in db_helpers.py:**
- ✅ get_current_profile()
- ✅ set_current_profile(profile_id)

**Need to add:**
- [ ] list_all_profiles() → List[Profile]
- [ ] create_profile_with_location(...) → Profile
- [ ] update_profile_field(profile_id, field, value)
- [ ] delete_profile(profile_id)
- [ ] invalidate_natal_cache(profile_id)
- [ ] create_location(...) → Location
- [ ] delete_location(location_id)
- [ ] check_location_in_use(location_id) → bool

## Future Enhancements

**Profile metadata:**
- Add notes field (for relationship context)
- Add tags (family, friend, client, etc.)
- Add avatar/photo support

**Location enhancements:**
- Geocoding API integration (auto-lookup coords)
- Location history (track moves)
- Favorite locations

**Multi-profile features:**
- Bulk operations (import multiple profiles)
- Profile groups (family, friends, clients)
- Profile sharing/export

## Questions for User

1. Should we allow deleting the only profile? Or require at least one?
2. Should set_current_profile(None) be allowed to "deactivate" all profiles?
3. Should we add a "notes" field to profiles for context?
4. Should location labels be unique, or allow duplicates?

## Completion Criteria

- [ ] All 7 tools implemented and tested
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Manual testing complete
- [ ] Merge to main

---

**Notes:**
- Keep stubs until implementation to maintain working state
- Implement incrementally (one tool at a time)
- Test each tool before moving to next
- Update ROADMAP.md when complete
