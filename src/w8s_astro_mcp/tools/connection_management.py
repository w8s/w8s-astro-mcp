"""Connection management MCP tools (Phase 7).

Tools for creating and managing synastry/composite/Davison connections
between astrological profiles.
"""

from datetime import datetime, timezone
from typing import Any
from mcp.types import Tool, TextContent


# ============================================================================
# Tool Definitions
# ============================================================================

def get_connection_tools() -> list[Tool]:
    """Return list of connection management tool definitions."""
    return [
        Tool(
            name="create_connection",
            description=(
                "Create a new connection between two or more profiles for synastry "
                "or composite/Davison chart analysis. "
                "Requires at least 2 profile IDs. "
                "Use list_profiles to find profile IDs first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Name for this connection (e.g., 'Alice & Bob', 'Family Trio')"
                    },
                    "profile_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of profile IDs to include (minimum 2)",
                        "minItems": 2
                    },
                    "type": {
                        "type": "string",
                        "description": "Optional connection type (e.g., 'romantic', 'family', 'business')"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Optional date the relationship began (YYYY-MM-DD)"
                    }
                },
                "required": ["label", "profile_ids"]
            }
        ),
        Tool(
            name="list_connections",
            description=(
                "List all connections with their member names and IDs. "
                "Use this to find connection IDs before requesting charts."
            ),
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="add_connection_member",
            description=(
                "Add a profile to an existing connection. "
                "Note: adding a member invalidates any cached charts for this connection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "integer",
                        "description": "Connection ID (from list_connections)"
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to add (from list_profiles)"
                    }
                },
                "required": ["connection_id", "profile_id"]
            }
        ),
        Tool(
            name="remove_connection_member",
            description=(
                "Remove a profile from a connection. "
                "Connection must retain at least 2 members. "
                "Note: removing a member invalidates any cached charts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "integer",
                        "description": "Connection ID (from list_connections)"
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to remove"
                    }
                },
                "required": ["connection_id", "profile_id"]
            }
        ),
        Tool(
            name="get_connection_chart",
            description=(
                "Calculate (or retrieve cached) a composite or Davison chart for a connection.\n\n"
                "COMPOSITE: Each planet position is the circular mean of all members' natal positions. "
                "No swetest call needed — pure math on cached natal data.\n\n"
                "DAVISON: A real chart cast for the midpoint datetime and location of all members' births. "
                "Requires a swetest call. Birth times are converted to UTC before averaging, "
                "so timezone data in each profile's birth location is used.\n\n"
                "Results are cached in the database. Use invalidate=true to force recalculation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "integer",
                        "description": "Connection ID (from list_connections)"
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["composite", "davison"],
                        "description": "Type of chart to calculate"
                    },
                    "invalidate": {
                        "type": "boolean",
                        "description": "Force recalculation even if cached (default: false)"
                    }
                },
                "required": ["connection_id", "chart_type"]
            }
        ),
        Tool(
            name="delete_connection",
            description=(
                "Delete a connection and all its cached charts. "
                "WARNING: Permanent and cannot be undone. "
                "Does not affect the member profiles themselves."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "integer",
                        "description": "Connection ID to delete"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to confirm deletion"
                    }
                },
                "required": ["connection_id", "confirm"]
            }
        ),
    ]


# ============================================================================
# Tool Handlers
# ============================================================================

async def handle_create_connection(db_helper, arguments: dict) -> list[TextContent]:
    """Create a new connection between profiles."""
    try:
        label = arguments.get("label")
        profile_ids = arguments.get("profile_ids", [])
        conn_type = arguments.get("type")
        start_date = arguments.get("start_date")

        if not label:
            return [TextContent(type="text", text="Error: label is required")]
        if len(profile_ids) < 2:
            return [TextContent(type="text", text="Error: at least 2 profile_ids are required")]

        # Verify all profiles exist
        missing = []
        profiles = []
        for pid in profile_ids:
            p = db_helper.get_profile_by_id(pid)
            if not p:
                missing.append(pid)
            else:
                profiles.append(p)
        if missing:
            return [TextContent(type="text", text=f"Error: profile(s) not found: {missing}")]

        # Create connection
        connection = db_helper.create_connection(
            label=label,
            profile_ids=profile_ids,
            type=conn_type,
            start_date=start_date,
        )

        member_names = ", ".join(p.name for p in profiles)
        response = f"✓ Connection created!\n\n"
        response += f"**{connection.label}** (ID: {connection.id})\n"
        if conn_type:
            response += f"Type: {conn_type}\n"
        if start_date:
            response += f"Since: {start_date}\n"
        response += f"Members: {member_names}\n\n"
        response += f"Use get_connection_chart with connection_id={connection.id} to calculate a chart."

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error creating connection: {e}")]


async def handle_list_connections(db_helper) -> list[TextContent]:
    """List all connections with member names."""
    try:
        connections = db_helper.list_all_connections()

        if not connections:
            return [TextContent(
                type="text",
                text="No connections found.\n\nUse create_connection to add one."
            )]

        response = "# Connections\n\n"
        for conn in connections:
            members = db_helper.get_connection_members(conn)
            member_names = ", ".join(m.name for m in members)
            response += f"**{conn.label}** (ID: {conn.id})\n"
            if conn.type:
                response += f"  Type: {conn.type}\n"
            response += f"  Members: {member_names}\n"
            if conn.start_date:
                response += f"  Since: {conn.start_date}\n"
            response += "\n"

        return [TextContent(type="text", text=response)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error listing connections: {e}")]


async def handle_add_connection_member(db_helper, arguments: dict) -> list[TextContent]:
    """Add a profile to a connection."""
    try:
        connection_id = arguments.get("connection_id")
        profile_id = arguments.get("profile_id")

        if connection_id is None or profile_id is None:
            return [TextContent(type="text", text="Error: connection_id and profile_id are required")]

        connection = db_helper.get_connection_by_id(connection_id)
        if not connection:
            return [TextContent(type="text", text=f"Error: connection {connection_id} not found")]

        profile = db_helper.get_profile_by_id(profile_id)
        if not profile:
            return [TextContent(type="text", text=f"Error: profile {profile_id} not found")]

        db_helper.add_connection_member(connection_id, profile_id)
        db_helper.invalidate_connection_charts(connection_id)

        return [TextContent(
            type="text",
            text=f"✓ Added **{profile.name}** to **{connection.label}**.\n\n"
                 "Cached charts have been invalidated. "
                 "Use get_connection_chart to recalculate."
        )]

    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error adding member: {e}")]


async def handle_remove_connection_member(db_helper, arguments: dict) -> list[TextContent]:
    """Remove a profile from a connection."""
    try:
        connection_id = arguments.get("connection_id")
        profile_id = arguments.get("profile_id")

        if connection_id is None or profile_id is None:
            return [TextContent(type="text", text="Error: connection_id and profile_id are required")]

        connection = db_helper.get_connection_by_id(connection_id)
        if not connection:
            return [TextContent(type="text", text=f"Error: connection {connection_id} not found")]

        profile = db_helper.get_profile_by_id(profile_id)
        if not profile:
            return [TextContent(type="text", text=f"Error: profile {profile_id} not found")]

        # Guard: must keep at least 2 members
        members = db_helper.get_connection_members(connection)
        if len(members) <= 2:
            return [TextContent(
                type="text",
                text=f"Error: cannot remove {profile.name} — a connection must have at least 2 members.\n\n"
                     "Use delete_connection to remove the whole connection instead."
            )]

        db_helper.remove_connection_member(connection_id, profile_id)
        db_helper.invalidate_connection_charts(connection_id)

        return [TextContent(
            type="text",
            text=f"✓ Removed **{profile.name}** from **{connection.label}**.\n\n"
                 "Cached charts have been invalidated."
        )]

    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error removing member: {e}")]


async def handle_get_connection_chart(db_helper, swetest, arguments: dict) -> list[TextContent]:
    """Calculate or retrieve a composite/Davison chart for a connection."""
    try:
        connection_id = arguments.get("connection_id")
        chart_type = arguments.get("chart_type")
        invalidate = arguments.get("invalidate", False)

        if connection_id is None or not chart_type:
            return [TextContent(type="text", text="Error: connection_id and chart_type are required")]

        connection = db_helper.get_connection_by_id(connection_id)
        if not connection:
            return [TextContent(type="text", text=f"Error: connection {connection_id} not found")]

        # Check cache
        cached = db_helper.get_connection_chart(connection_id, chart_type)
        if cached and cached.is_valid and not invalidate:
            return _format_cached_chart(connection, cached, db_helper)

        # Need to calculate — gather member natal data
        members = db_helper.get_connection_members(connection)
        if len(members) < 2:
            return [TextContent(type="text", text="Error: connection needs at least 2 members")]

        # Import here to avoid circular deps
        from ..utils.connection_calculator import (
            calculate_composite_positions,
            calculate_davison_midpoint,
            enrich_natal_chart_for_composite,
        )

        if chart_type == "composite":
            # Pull natal chart data for each member
            natal_charts = []
            for member in members:
                chart_data = db_helper.get_natal_chart_data(member)
                if not chart_data or not chart_data.get("planets"):
                    return [TextContent(
                        type="text",
                        text=f"Error: no natal chart data for {member.name}. "
                             "Run get_natal_chart for this profile first."
                    )]
                enriched = enrich_natal_chart_for_composite(chart_data)
                natal_charts.append(enriched)

            positions = calculate_composite_positions(natal_charts)

            # Save to DB
            chart = db_helper.save_connection_chart(
                connection_id=connection_id,
                chart_type="composite",
                positions=positions,
                calculation_method="circular_mean",
            )
            return _format_chart_result(connection, chart, positions, members, "Composite")

        elif chart_type == "davison":
            if swetest is None:
                return [TextContent(
                    type="text",
                    text="Error: swetest is not available. "
                         "Run check_swetest_installation for setup instructions."
                )]

            # Get birth locations for timezone-aware midpoint calc
            birth_locations = []
            for member in members:
                loc = db_helper.get_birth_location(member)
                if not loc:
                    return [TextContent(
                        type="text",
                        text=f"Error: no birth location for {member.name}. "
                             "Cannot calculate Davison midpoint without timezone data."
                    )]
                birth_locations.append(loc)

            midpoint = calculate_davison_midpoint(members, birth_locations)

            # Cast real chart at midpoint via swetest
            raw = swetest.get_transits(
                latitude=midpoint["latitude"],
                longitude=midpoint["longitude"],
                date_str=midpoint["date"],
                time_str=midpoint["time"],
                house_system_code="P",
            )

            # Save to DB
            chart = db_helper.save_connection_chart(
                connection_id=connection_id,
                chart_type="davison",
                positions=raw,
                davison_midpoint=midpoint,
                calculation_method="pysweph",
            )
            return _format_chart_result(connection, chart, raw, members, "Davison", midpoint)

        else:
            return [TextContent(type="text", text=f"Error: unknown chart_type '{chart_type}'")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error calculating chart: {e}")]


async def handle_delete_connection(db_helper, arguments: dict) -> list[TextContent]:
    """Delete a connection."""
    try:
        connection_id = arguments.get("connection_id")
        confirm = arguments.get("confirm")

        if connection_id is None:
            return [TextContent(type="text", text="Error: connection_id is required")]
        if confirm is not True:
            return [TextContent(
                type="text",
                text="Error: set confirm=true to delete.\n\n"
                     "This permanently removes the connection and all cached charts."
            )]

        connection = db_helper.get_connection_by_id(connection_id)
        if not connection:
            return [TextContent(type="text", text=f"Error: connection {connection_id} not found")]

        label = connection.label
        db_helper.delete_connection(connection_id)

        return [TextContent(
            type="text",
            text=f"✓ Connection **{label}** (ID: {connection_id}) deleted.\n\n"
                 "Member profiles are unaffected."
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Error deleting connection: {e}")]


# ============================================================================
# Formatting helpers
# ============================================================================

def _format_chart_result(connection, chart, positions, members, chart_label, midpoint=None):
    """Format a freshly-calculated chart for display."""
    member_names = ", ".join(m.name for m in members)
    response = f"# {chart_label} Chart — {connection.label}\n\n"
    response += f"Members: {member_names}\n"
    if midpoint:
        response += f"Midpoint: {midpoint['date']} {midpoint['time']} UTC\n"
        response += f"Location: {midpoint['latitude']:.4f}, {midpoint['longitude']:.4f}\n"
    response += f"Calculated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n\n"

    planets = positions.get("planets", {})
    if planets:
        response += "## Planets\n"
        for name, data in planets.items():
            pos = data.get("formatted") or _fmt(data)
            response += f"- **{name}**: {pos}\n"
        response += "\n"

    houses = positions.get("houses", {})
    if houses:
        response += "## Houses\n"
        for num in sorted(houses.keys(), key=lambda x: int(x)):
            data = houses[num]
            pos = data.get("formatted") or _fmt(data)
            response += f"- House {num}: {pos}\n"
        response += "\n"

    points = positions.get("points", {})
    if points:
        response += "## Angles\n"
        for name, data in points.items():
            pos = data.get("formatted") or _fmt(data)
            response += f"- **{name}**: {pos}\n"

    return [TextContent(type="text", text=response)]


def _format_cached_chart(connection, cached_chart, db_helper):
    """Format a cached chart for display."""
    response = f"# {cached_chart.chart_type.title()} Chart — {connection.label} (cached)\n\n"
    if cached_chart.davison_date:
        response += f"Midpoint: {cached_chart.davison_date} {cached_chart.davison_time} UTC\n"
        response += f"Location: {cached_chart.davison_latitude:.4f}, {cached_chart.davison_longitude:.4f}\n"
    response += f"Calculated: {cached_chart.calculated_at}\n\n"

    planets = db_helper.get_connection_planets(cached_chart.id)
    if planets:
        response += "## Planets\n"
        for p in planets:
            response += f"- **{p.planet}**: {p.formatted_position}\n"
        response += "\n"

    houses = db_helper.get_connection_houses(cached_chart.id)
    if houses:
        response += "## Houses\n"
        for h in sorted(houses, key=lambda x: x.house_number):
            response += f"- House {h.house_number}: {h.formatted_position}\n"
        response += "\n"

    points = db_helper.get_connection_points(cached_chart.id)
    if points:
        response += "## Angles\n"
        for pt in points:
            response += f"- **{pt.point_type}**: {pt.formatted_position}\n"

    return [TextContent(type="text", text=response)]


def _fmt(data: dict) -> str:
    """Fallback formatter for position data lacking a 'formatted' key."""
    if "sign" in data and "degree" in data:
        return f"{data['degree']}° {data.get('minutes', 0):02d}' {data['sign']}"
    if "absolute_position" in data:
        return f"{data['absolute_position']:.2f}°"
    return str(data)


# ============================================================================
# Router
# ============================================================================

CONNECTION_TOOL_NAMES = {
    "create_connection",
    "list_connections",
    "add_connection_member",
    "remove_connection_member",
    "get_connection_chart",
    "delete_connection",
}


async def handle_connection_tool(
    name: str, arguments: Any, db_helper, swetest=None
) -> list[TextContent]:
    """Route connection tool calls to appropriate handlers."""
    if name == "create_connection":
        return await handle_create_connection(db_helper, arguments)
    elif name == "list_connections":
        return await handle_list_connections(db_helper)
    elif name == "add_connection_member":
        return await handle_add_connection_member(db_helper, arguments)
    elif name == "remove_connection_member":
        return await handle_remove_connection_member(db_helper, arguments)
    elif name == "get_connection_chart":
        return await handle_get_connection_chart(db_helper, swetest, arguments)
    elif name == "delete_connection":
        return await handle_delete_connection(db_helper, arguments)
    else:
        return [TextContent(type="text", text=f"Unknown connection tool: {name}")]
