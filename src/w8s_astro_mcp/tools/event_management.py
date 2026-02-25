"""Event chart management MCP tools (Phase 8).

Tools for casting, saving, listing, and deleting event charts.
Event charts are cast for a specific moment in time and place —
no profile required. Useful for historical events, mundane charts,
and as the foundation for electional astrology scanning.
"""

from typing import Any
from mcp.types import Tool, TextContent


# ============================================================================
# Tool Definitions
# ============================================================================

def get_event_tools() -> list[Tool]:
    """Return list of event chart tool definitions."""
    return [
        Tool(
            name="cast_event_chart",
            description=(
                "Cast an astrological chart for any date, time, and location. "
                "No profile required — useful for historical events, mundane astrology, "
                "and electional work.\n\n"
                "If 'label' is provided, the chart is saved to the database and can be "
                "referenced later via compare_charts using 'event:<label>'.\n\n"
                "If 'label' is omitted, the chart is calculated and returned but not saved."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM format (local time at the given location)"
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
                        "description": "IANA timezone name (e.g., 'America/Chicago')"
                    },
                    "location_name": {
                        "type": "string",
                        "description": "Human-readable location name (e.g., 'Chicago, IL')"
                    },
                    "label": {
                        "type": "string",
                        "description": (
                            "Optional unique name to save this chart for later reference. "
                            "If omitted, chart is calculated but not saved. "
                            "Must be unique among all saved event charts."
                        )
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional notes about this event"
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Optional profile ID to associate this event with a person"
                    }
                },
                "required": ["date", "time", "latitude", "longitude", "timezone", "location_name"]
            }
        ),
        Tool(
            name="list_event_charts",
            description=(
                "List all saved event charts. "
                "Shows label, date/time, location, and optional description. "
                "Saved charts can be used in compare_charts via 'event:<label>'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_id": {
                        "type": "integer",
                        "description": "Optional: filter to events associated with a specific profile"
                    }
                }
            }
        ),
        Tool(
            name="delete_event_chart",
            description=(
                "Delete a saved event chart by label. "
                "WARNING: Permanent and cannot be undone."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Label of the event chart to delete"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to confirm deletion"
                    }
                },
                "required": ["label", "confirm"]
            }
        ),
        Tool(
            name="find_electional_windows",
            description=(
                "Scan a time window and return candidate moments that satisfy "
                "electional astrology criteria. Useful for finding auspicious times "
                "to start a project, sign a contract, hold an event, etc.\n\n"
                "Scans at a configurable interval (default 60 minutes) and scores "
                "each moment against the requested criteria. Returns candidates ranked "
                "by score (most criteria met first), then by tightness.\n\n"
                "Maximum window: 90 days. Maximum interval: 360 minutes (6 hours). "
                "Minimum interval: 15 minutes.\n\n"
                "Available criteria:\n"
                "- moon_not_void: Moon is not void of course\n"
                "- no_retrograde_inner: Mercury and Venus are direct\n"
                "- no_retrograde_outer: Mars through Pluto are direct\n"
                "- no_retrograde_all: All planets are direct\n"
                "- moon_waxing: Moon is waxing (New to Full)\n"
                "- moon_waning: Moon is waning (Full to New)\n"
                "- benefic_angular: Venus or Jupiter in houses 1, 4, 7, or 10\n"
                "- asc_not_late: Ascendant is not in the last 3° of its sign"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start of scan window (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of scan window (YYYY-MM-DD, max 90 days from start)"
                    },
                    "latitude": {
                        "type": "number",
                        "description": "Latitude for the charts"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude for the charts"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone for display and local-time interpretation"
                    },
                    "location_name": {
                        "type": "string",
                        "description": "Human-readable location name"
                    },
                    "criteria": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "moon_not_void",
                                "no_retrograde_inner",
                                "no_retrograde_outer",
                                "no_retrograde_all",
                                "moon_waxing",
                                "moon_waning",
                                "benefic_angular",
                                "asc_not_late"
                            ]
                        },
                        "description": "Criteria to evaluate at each interval",
                        "minItems": 1
                    },
                    "interval_minutes": {
                        "type": "integer",
                        "description": "Minutes between scan steps (15–360, default 60)",
                        "minimum": 15,
                        "maximum": 360
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of candidates to return (default 10)",
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": [
                    "start_date", "end_date",
                    "latitude", "longitude", "timezone", "location_name",
                    "criteria"
                ]
            }
        ),
    ]


# ============================================================================
# Tool Handlers
# ============================================================================

async def handle_cast_event_chart(db_helper, arguments: dict) -> list[TextContent]:
    """Cast a chart for an event date/time/location. Optionally save it."""
    date = arguments.get("date", "").strip()
    time = arguments.get("time", "12:00").strip()
    latitude = arguments.get("latitude")
    longitude = arguments.get("longitude")
    timezone = arguments.get("timezone", "UTC").strip()
    location_name = arguments.get("location_name", "").strip()
    label = arguments.get("label", "").strip() or None
    description = arguments.get("description", "").strip() or None
    profile_id = arguments.get("profile_id")

    if not date:
        return [TextContent(type="text", text="Error: date is required")]
    if latitude is None or longitude is None:
        return [TextContent(type="text", text="Error: latitude and longitude are required")]

    from ..utils.ephemeris import EphemerisEngine, EphemerisError
    try:
        engine = EphemerisEngine()
        chart = engine.get_chart(
            latitude=latitude,
            longitude=longitude,
            date_str=date,
            time_str=time,
        )
    except EphemerisError as e:
        return [TextContent(type="text", text=f"Error calculating chart: {e}")]

    # Format output
    planets = chart.get("planets", {})
    houses = chart.get("houses", {})
    points = chart.get("points", {})

    lines = [
        f"# Event Chart: {label or 'Ad-hoc'}",
        f"**Date:** {date} at {time}",
        f"**Location:** {location_name} ({latitude:.3f}, {longitude:.3f})",
        f"**Timezone:** {timezone}",
    ]
    if description:
        lines.append(f"**Notes:** {description}")
    lines.append("")

    # Angles
    if points:
        lines.append("## Angles")
        for name, pos in points.items():
            lines.append(f"- **{name}**: {pos.get('degree', 0):.2f}° {pos.get('sign', '')}")
        lines.append("")

    # Planets
    if planets:
        lines.append("## Planets")
        for planet, pos in planets.items():
            retro = " ℞" if pos.get("is_retrograde") else ""
            house = f" (H{pos.get('house_number', '?')})" if pos.get("house_number") else ""
            lines.append(f"- **{planet}**: {pos.get('degree', 0):.2f}° {pos.get('sign', '')}{retro}{house}")
        lines.append("")

    # Houses
    if houses:
        lines.append("## House Cusps")
        for num in sorted(houses.keys(), key=lambda x: int(x)):
            pos = houses[num]
            lines.append(f"- **House {num}**: {pos.get('degree', 0):.2f}° {pos.get('sign', '')}")
        lines.append("")

    saved_msg = ""
    if label:
        try:
            db_helper.save_event_chart(
                label=label,
                event_date=date,
                event_time=time,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                location_name=location_name,
                description=description,
                profile_id=profile_id,
                chart=chart,
            )
            saved_msg = f"\n✓ Saved as **\"{label}\"** — reference with `compare_charts` using `event:{label}`"
        except Exception as e:
            saved_msg = f"\n⚠ Chart calculated but not saved: {e}"

    lines.append(saved_msg.strip() if saved_msg else "_Chart not saved (no label provided)_")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_list_event_charts(db_helper, arguments: dict) -> list[TextContent]:
    """List all saved event charts."""
    profile_id = arguments.get("profile_id")

    try:
        events = db_helper.list_event_charts(profile_id=profile_id)
    except Exception as e:
        return [TextContent(type="text", text=f"Error listing event charts: {e}")]

    if not events:
        filter_msg = f" for profile {profile_id}" if profile_id else ""
        return [TextContent(
            type="text",
            text=f"No saved event charts found{filter_msg}.\n\nUse `cast_event_chart` with a `label` to save one."
        )]

    lines = ["# Saved Event Charts", ""]
    for ev in events:
        lines.append(f"## {ev.label}")
        lines.append(f"- **Date/Time:** {ev.event_date} at {ev.event_time}")
        lines.append(f"- **Location:** {ev.location_name} ({ev.latitude:.3f}, {ev.longitude:.3f})")
        if ev.profile_id:
            lines.append(f"- **Profile ID:** {ev.profile_id}")
        if ev.description:
            lines.append(f"- **Notes:** {ev.description}")
        lines.append(f"- **Reference:** `event:{ev.label}`")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_delete_event_chart(db_helper, arguments: dict) -> list[TextContent]:
    """Delete a saved event chart by label."""
    label = arguments.get("label", "").strip()
    confirm = arguments.get("confirm", False)

    if not label:
        return [TextContent(type="text", text="Error: label is required")]
    if not confirm:
        return [TextContent(type="text", text="Error: confirm must be true to delete an event chart")]

    try:
        deleted = db_helper.delete_event_chart(label=label)
    except Exception as e:
        return [TextContent(type="text", text=f"Error deleting event chart: {e}")]

    if not deleted:
        return [TextContent(type="text", text=f"Event chart \"{label}\" not found")]

    return [TextContent(type="text", text=f"✓ Event chart \"{label}\" deleted")]


async def handle_find_electional_windows(db_helper, arguments: dict) -> list[TextContent]:
    """Scan a time window for moments satisfying electional criteria."""
    from datetime import datetime, timedelta

    start_date = arguments.get("start_date", "").strip()
    end_date = arguments.get("end_date", "").strip()
    latitude = arguments.get("latitude")
    longitude = arguments.get("longitude")
    timezone = arguments.get("timezone", "UTC").strip()
    location_name = arguments.get("location_name", "").strip()
    criteria = arguments.get("criteria", [])
    interval_minutes = int(arguments.get("interval_minutes", 60))
    max_results = int(arguments.get("max_results", 10))

    # Validate before importing heavy ephemeris module
    if not start_date or not end_date:
        return [TextContent(type="text", text="Error: start_date and end_date are required")]
    if latitude is None or longitude is None:
        return [TextContent(type="text", text="Error: latitude and longitude are required")]
    if not criteria:
        return [TextContent(type="text", text="Error: at least one criterion is required")]

    interval_minutes = max(15, min(360, interval_minutes))
    max_results = max(1, min(50, max_results))

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        return [TextContent(type="text", text=f"Error parsing dates: {e}")]

    window_days = (end_dt - start_dt).days
    if window_days > 90:
        return [TextContent(type="text", text="Error: window cannot exceed 90 days")]
    if window_days < 0:
        return [TextContent(type="text", text="Error: end_date must be after start_date")]

    from ..utils.ephemeris import EphemerisEngine, EphemerisError
    from ..utils.electional import score_chart
    engine = EphemerisEngine()
    candidates = []
    current = start_dt
    step = timedelta(minutes=interval_minutes)

    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%d")
        time_str = current.strftime("%H:%M")
        try:
            chart = engine.get_chart(
                latitude=latitude,
                longitude=longitude,
                date_str=date_str,
                time_str=time_str,
            )
            met, details = score_chart(chart, criteria)
            if met:
                candidates.append((len(met), current, met, details))
        except EphemerisError:
            pass  # Skip bad timestamps silently
        current += step

    if not candidates:
        return [TextContent(
            type="text",
            text=(
                f"No candidates found in {start_date} – {end_date} at {interval_minutes}-minute intervals.\n\n"
                "Try widening the window, increasing the interval, or reducing criteria."
            )
        )]

    # Sort by score desc, then by datetime asc
    candidates.sort(key=lambda x: (-x[0], x[1]))
    candidates = candidates[:max_results]

    lines = [
        f"# Electional Windows: {start_date} – {end_date}",
        f"**Location:** {location_name}",
        f"**Criteria:** {', '.join(criteria)}",
        f"**Interval:** {interval_minutes} min | **Results:** {len(candidates)} of {max_results} max",
        "",
    ]

    for i, (score, dt, met_criteria, details) in enumerate(candidates, 1):
        lines.append(f"## {i}. {dt.strftime('%Y-%m-%d %H:%M')} — {score}/{len(criteria)} criteria met")
        for c in met_criteria:
            lines.append(f"  ✓ {c}")
        for c in criteria:
            if c not in met_criteria:
                note = details.get(c, "")
                lines.append(f"  ✗ {c}" + (f" ({note})" if note else ""))
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


# ============================================================================
# Tool name registry + dispatcher
# ============================================================================

EVENT_TOOL_NAMES = {
    "cast_event_chart",
    "list_event_charts",
    "delete_event_chart",
    "find_electional_windows",
}


async def handle_event_tool(
    name: str, arguments: dict, db_helper, swetest=None
) -> list[TextContent]:
    """Route event tool calls to the appropriate handler."""
    if name == "cast_event_chart":
        return await handle_cast_event_chart(db_helper, arguments)
    elif name == "list_event_charts":
        return await handle_list_event_charts(db_helper, arguments)
    elif name == "delete_event_chart":
        return await handle_delete_event_chart(db_helper, arguments)
    elif name == "find_electional_windows":
        return await handle_find_electional_windows(db_helper, arguments)
    else:
        return [TextContent(type="text", text=f"Unknown event tool: {name}")]
