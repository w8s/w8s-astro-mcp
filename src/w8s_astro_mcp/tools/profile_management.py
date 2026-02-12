"""Profile management MCP tools.

Tools for creating, updating, and managing astrological profiles.
Enables multi-profile support for friends, family, synastry, etc.
"""

from typing import Any, Optional
from mcp.types import Tool, TextContent


# ============================================================================
# Tool Definitions
# ============================================================================

def get_profile_management_tools() -> list[Tool]:
    """Return list of profile management tool definitions."""
    return [
        Tool(
            name="list_profiles",
            description=(
                "List all astrological profiles in the database. "
                "Shows profile names, birth dates, and which is currently active. "
                "Use this to see all available profiles before creating, updating, or switching."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="create_profile",
            description=(
                "Create a new astrological profile (for friends, family, synastry analysis, etc.). "
                "After creating, ask user if this should be their current profile. "
                "IMPORTANT: Ask for information conversationally:\n"
                "1. Ask: 'What's their name?'\n"
                "2. Ask: 'What's their birthday?' (get YYYY-MM-DD)\n"
                "3. Ask: 'Do you know what time they were born? (If not, we can use 12:00)'\n"
                "4. Ask: 'Where were they born?' (get city, state/country)\n"
                "Then look up coordinates and confirm before saving."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Person's name (e.g., 'Sarah Johnson')"
                    },
                    "birth_date": {
                        "type": "string",
                        "description": "Birth date in YYYY-MM-DD format"
                    },
                    "birth_time": {
                        "type": "string",
                        "description": "Birth time in HH:MM format (24-hour)"
                    },
                    "birth_location_name": {
                        "type": "string",
                        "description": "Location name (e.g., 'New York, NY')"
                    },
                    "birth_latitude": {
                        "type": "number",
                        "description": "Latitude in decimal degrees"
                    },
                    "birth_longitude": {
                        "type": "number",
                        "description": "Longitude in decimal degrees"
                    },
                    "birth_timezone": {
                        "type": "string",
                        "description": "Timezone (e.g., 'America/New_York')"
                    }
                },
                "required": ["name", "birth_date", "birth_time", "birth_location_name",
                           "birth_latitude", "birth_longitude", "birth_timezone"]
            }
        ),
        Tool(
            name="update_profile",
            description=(
                "Update a profile field (name, birth date, birth time, etc.). "
                "Use with caution - changing birth data invalidates cached natal chart. "
                "Valid fields: name, birth_date, birth_time"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to update (get from list_profiles)"
                    },
                    "field": {
                        "type": "string",
                        "description": "Field to update (name, birth_date, birth_time)",
                        "enum": ["name", "birth_date", "birth_time"]
                    },
                    "value": {
                        "type": "string",
                        "description": "New value for the field"
                    }
                },
                "required": ["profile_id", "field", "value"]
            }
        ),
        Tool(
            name="delete_profile",
            description=(
                "Delete a profile from the database. "
                "WARNING: This is permanent and cannot be undone. "
                "Deletes the profile and all associated natal chart data. "
                "If this is the current profile, current_profile_id will be set to NULL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to delete (get from list_profiles)"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to confirm deletion"
                    }
                },
                "required": ["profile_id", "confirm"]
            }
        ),
        Tool(
            name="set_current_profile",
            description=(
                "Switch the active profile (whose chart is 'yours'). "
                "This determines which profile is used for get_natal_chart, "
                "get_transits, and other operations. "
                "Use after creating a new profile or to switch between profiles."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to set as current (get from list_profiles)"
                    }
                },
                "required": ["profile_id"]
            }
        ),
        Tool(
            name="add_location",
            description=(
                "Add a saved location (home, office, travel destination, etc.) for a profile. "
                "Every location must belong to a specific profile."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID this location belongs to (required)"
                    },
                    "label": {
                        "type": "string",
                        "description": "Location label (e.g., 'Office', 'Vacation Home')"
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Latitude in decimal degrees"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude in decimal degrees"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (e.g., 'America/Los_Angeles')"
                    },
                    "set_as_home": {
                        "type": "boolean",
                        "description": "Optional: Set as current home location for this profile"
                    }
                },
                "required": ["profile_id", "label", "latitude", "longitude", "timezone"]
            }
        ),
        Tool(
            name="remove_location",
            description=(
                "Remove a saved location. "
                "WARNING: Cannot remove locations that are set as birth locations for profiles."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "location_id": {
                        "type": "integer",
                        "description": "Location ID to remove (get from view_config)"
                    }
                },
                "required": ["location_id"]
            }
        ),
    ]


# ============================================================================
# Tool Handlers
# ============================================================================

async def handle_list_profiles(db_helper) -> list[TextContent]:
    """List all profiles in database."""
    try:
        # Get all profiles
        profiles = db_helper.list_all_profiles()
        
        # Get current profile ID
        current_profile = db_helper.get_current_profile()
        current_id = current_profile.id if current_profile else None
        
        # Handle empty case
        if not profiles:
            return [TextContent(
                type="text",
                text="No profiles found in database.\n\n"
                     "Use create_profile to add your first profile."
            )]
        
        # Format profile list
        response = "# Astrological Profiles\n\n"
        
        for profile in profiles:
            # Current profile indicator
            indicator = "* " if profile.id == current_id else "  "
            
            # Format line
            response += f"{indicator}**{profile.name}** (ID: {profile.id})\n"
            response += f"  Born: {profile.birth_date} at {profile.birth_time}\n"
            
            # Birth location if available
            birth_loc = db_helper.get_birth_location(profile)
            if birth_loc:
                response += f"  Location: {birth_loc.label}\n"
            
            response += "\n"
        
        # Add legend
        if current_id:
            response += "*Current active profile\n"
        else:
            response += "No current profile set. Use set_current_profile to activate one.\n"
        
        return [TextContent(type="text", text=response)]
        
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error listing profiles: {e}"
        )]


async def handle_create_profile(db_helper, arguments: dict) -> list[TextContent]:
    """Create a new profile."""
    try:
        # Extract arguments
        name = arguments.get("name")
        birth_date = arguments.get("birth_date")
        birth_time = arguments.get("birth_time")
        birth_location_name = arguments.get("birth_location_name")
        birth_latitude = arguments.get("birth_latitude")
        birth_longitude = arguments.get("birth_longitude")
        birth_timezone = arguments.get("birth_timezone")
        
        # Validate required fields
        if not all([name, birth_date, birth_time, birth_location_name, 
                   birth_latitude, birth_longitude, birth_timezone]):
            return [TextContent(
                type="text",
                text="Error: All fields are required (name, birth_date, birth_time, "
                     "birth_location_name, birth_latitude, birth_longitude, birth_timezone)"
            )]
        
        # Create profile with birth location
        profile = db_helper.create_profile_with_location(
            name=name,
            birth_date=birth_date,
            birth_time=birth_time,
            birth_location_name=birth_location_name,
            birth_latitude=birth_latitude,
            birth_longitude=birth_longitude,
            birth_timezone=birth_timezone
        )
        
        # Format success message
        response = f"✓ Profile created successfully!\n\n"
        response += f"**{profile.name}** (ID: {profile.id})\n"
        response += f"Born: {profile.birth_date} at {profile.birth_time}\n"
        response += f"Location: {birth_location_name}\n"
        response += f"Coordinates: {birth_latitude}, {birth_longitude}\n"
        response += f"Timezone: {birth_timezone}\n\n"
        response += "Would you like to set this as your current profile?\n"
        response += f"Use: set_current_profile with profile_id={profile.id}"
        
        return [TextContent(type="text", text=response)]
        
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error creating profile: {e}"
        )]


async def handle_update_profile(db_helper, arguments: dict) -> list[TextContent]:
    """Update a profile field."""
    # TODO: Implement
    # 1. Validate profile exists
    # 2. Validate field name
    # 3. Update field
    # 4. If birth_date or birth_time changed, invalidate natal chart cache
    return [TextContent(
        type="text",
        text="🚧 update_profile - Not yet implemented\n\n"
             f"Would update profile {arguments.get('profile_id')}\n"
             f"Field: {arguments.get('field')}\n"
             f"New value: {arguments.get('value')}"
    )]


async def handle_delete_profile(db_helper, arguments: dict) -> list[TextContent]:
    """Delete a profile."""
    # TODO: Implement
    # 1. Check confirm=true
    # 2. Check profile exists
    # 3. Delete profile (CASCADE will delete natal chart data)
    # 4. If was current_profile, set to NULL
    return [TextContent(
        type="text",
        text="🚧 delete_profile - Not yet implemented\n\n"
             f"Would delete profile {arguments.get('profile_id')}\n"
             f"Confirmed: {arguments.get('confirm')}"
    )]


async def handle_set_current_profile(db_helper, arguments: dict) -> list[TextContent]:
    """Set the current active profile."""
    try:
        profile_id = arguments.get("profile_id")
        
        # Validate profile_id provided
        if profile_id is None:
            return [TextContent(
                type="text",
                text="Error: profile_id is required"
            )]
        
        # Use existing db_helper method (validates profile exists)
        success = db_helper.set_current_profile(profile_id)
        
        if not success:
            return [TextContent(
                type="text",
                text=f"Error: Profile with ID {profile_id} not found.\n\n"
                     "Use list_profiles to see available profiles."
            )]
        
        # Get the profile to show confirmation
        profile = db_helper.get_profile_by_id(profile_id)
        
        return [TextContent(
            type="text",
            text=f"✓ Current profile set to: **{profile.name}** (ID: {profile_id})\n\n"
                 f"Born: {profile.birth_date} at {profile.birth_time}\n\n"
                 "This profile will now be used for:\n"
                 "- get_natal_chart\n"
                 "- get_transits (default location)\n"
                 "- compare_charts (when using 'natal')"
        )]
        
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error setting current profile: {e}"
        )]


async def handle_add_location(db_helper, arguments: dict) -> list[TextContent]:
    """Add a saved location to a profile."""
    try:
        # Extract arguments
        profile_id = arguments.get("profile_id")
        label = arguments.get("label")
        latitude = arguments.get("latitude")
        longitude = arguments.get("longitude")
        timezone = arguments.get("timezone")
        set_as_home = arguments.get("set_as_home", False)
        
        # Validate required fields
        if not all([profile_id, label, latitude, longitude, timezone]):
            return [TextContent(
                type="text",
                text="Error: Missing required fields (profile_id, label, latitude, longitude, timezone)"
            )]
        
        # Verify profile exists
        profile = db_helper.get_profile_by_id(profile_id)
        if not profile:
            return [TextContent(
                type="text",
                text=f"Error: Profile {profile_id} not found. Use list_profiles to see available profiles."
            )]
        
        # Create location
        location = db_helper.create_location(
            profile_id=profile_id,
            label=label,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            set_as_home=set_as_home
        )
        
        # Format success message
        response = f"✓ Location added successfully!\n\n"
        response += f"**{label}** (ID: {location.id})\n"
        response += f"Profile: {profile.name} (ID: {profile.id})\n"
        response += f"Coordinates: {latitude}, {longitude}\n"
        response += f"Timezone: {timezone}\n"
        
        if set_as_home:
            response += f"\n✓ Set as current home location for {profile.name}"
        else:
            response += f"\nNot set as home. To make this the home location, use add_location with set_as_home=true"
        
        return [TextContent(type="text", text=response)]
        
    except ValueError as e:
        # Profile not found error from create_location
        return [TextContent(
            type="text",
            text=f"Error: {e}. Use list_profiles to see available profiles."
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error adding location: {e}"
        )]


async def handle_remove_location(db_helper, arguments: dict) -> list[TextContent]:
    """Remove a saved location."""
    # TODO: Implement
    # 1. Check location exists
    # 2. Check not used as birth_location
    # 3. Delete location
    return [TextContent(
        type="text",
        text="🚧 remove_location - Not yet implemented\n\n"
             f"Would remove location ID: {arguments.get('location_id')}"
    )]


# ============================================================================
# Router
# ============================================================================

async def handle_profile_tool(name: str, arguments: Any, db_helper) -> list[TextContent]:
    """Route profile management tool calls to appropriate handlers."""
    
    handlers = {
        "list_profiles": handle_list_profiles,
        "create_profile": handle_create_profile,
        "update_profile": handle_update_profile,
        "delete_profile": handle_delete_profile,
        "set_current_profile": handle_set_current_profile,
        "add_location": handle_add_location,
        "remove_location": handle_remove_location,
    }
    
    handler = handlers.get(name)
    if not handler:
        return [TextContent(type="text", text=f"Unknown profile tool: {name}")]
    
    # Call handler (some take arguments, some don't)
    if name == "list_profiles":
        return await handler(db_helper)
    else:
        return await handler(db_helper, arguments)
