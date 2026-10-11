"""Chart tools: natal charts, house placements, chart comparison and the natal chart image.

Also holds the two chart helpers the other tools share: `get_natal_chart_data` (a profile's natal
chart, calculated and stored on first use) and `get_chart_for_date` (the sky at a place and moment).
"""

import logging
from typing import Any, Dict, Optional

from mcp.types import TextContent, Tool

from ..utils.messages import profile_not_found, profiles_not_found
from ..registry import ToolContext, ToolSpec, bind_handlers
from ..utils.ephemeris import EphemerisError
from ..utils.timezones import TimezoneError, utc_engine_args
from .analysis_tools import (
    AnalysisError,
    INCLUDE_ANGLES_MODES,
    compare_charts,
    find_planets_in_houses,
    format_aspect_json,
    format_aspect_report,
    format_house_report,
)
from .placement_dials import (
    DEFAULT_TITLE as PLACEMENT_DIALS_TITLE,
    create_placement_dials,
    open_in_default_browser,
    slugify as placement_dials_slug,
)
from .visualization import create_natal_chart

logger = logging.getLogger(__name__)


# ============================================================================
# Tool Definitions
# ============================================================================

def get_chart_tools() -> list[Tool]:
    return [
        Tool(
            name="get_natal_chart",
            description="Get the natal chart (birth chart) planetary positions for a profile. Defaults to the owner profile if no profile_id is supplied.",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to query (from list_profiles). Defaults to owner profile."
                    }
                }
            }
        ),
        Tool(
            name="visualize_natal_chart",
            description="Generate a circular natal chart visualization and save to file. Creates a traditional astrological chart wheel with zodiac signs, houses, planets, and angles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Path where to save the chart image (e.g., '~/Downloads/natal_chart.png'). Defaults to 'natal_chart.png' in current directory."
                    },
                    "title": {
                        "type": "string",
                        "description": "Custom title for the chart (optional, defaults to 'Natal Chart')"
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to visualize (from list_profiles). Defaults to owner profile."
                    }
                }
            }
        ),
        Tool(
            name="compare_charts",
            description=(
                "Calculate aspects between two charts. "
                "Use for synastry (comparing two natal charts), transits (comparing natal chart with current positions), "
                "or event chart analysis. "
                "Finds conjunctions, oppositions, trines, squares, sextiles, and minor aspects. "
                "Each aspect names the chart each body belongs to (natal, transit, event) and, "
                "when a chart carries planet speeds (transit charts), whether the aspect is applying "
                "or separating with an estimated time of exactness. "
                "Times are UT. Transit-chart angles use the owner's current home location."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chart1_date": {
                        "type": "string",
                        "description": "Date for first chart (YYYY-MM-DD), use 'natal' for a natal chart, or 'event:<label>' for a saved event chart"
                    },
                    "chart1_time": {
                        "type": "string",
                        "description": "Time for first chart in HH:MM format, interpreted as UT (optional, defaults to 12:00)"
                    },
                    "chart1_profile_id": {
                        "type": "integer",
                        "description": "Profile ID for chart1 when chart1_date is 'natal' (from list_profiles). Defaults to owner profile."
                    },
                    "chart2_date": {
                        "type": "string",
                        "description": "Date for second chart (YYYY-MM-DD), use 'natal' for a natal chart, 'today' for current, or 'event:<label>' for a saved event chart"
                    },
                    "chart2_time": {
                        "type": "string",
                        "description": "Time for second chart in HH:MM format, interpreted as UT (optional, defaults to 12:00)"
                    },
                    "chart2_profile_id": {
                        "type": "integer",
                        "description": "Profile ID for chart2 when chart2_date is 'natal' (from list_profiles). Defaults to owner profile."
                    },
                    "orb_multiplier": {
                        "type": "number",
                        "description": "Multiplier for aspect orbs (optional, default 1.0)"
                    },
                    "planets_only": {
                        "type": "boolean",
                        "description": (
                            "Legacy switch, kept for compatibility: true (default) compares planets only; "
                            "false also compares the angles of both charts. Prefer include_angles, which overrides this."
                        )
                    },
                    "include_angles": {
                        "type": "string",
                        "enum": ["none", "natal", "transit", "both"],
                        "description": (
                            "Which charts contribute their angles (Ascendant, MC, etc.). 'natal' uses only the natal "
                            "chart's angles - the usual choice for transits, since the transit sky's own angles change "
                            "every few minutes and add noise. Overrides planets_only. Default: none."
                        )
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": (
                            "Output format. 'text' (default) is human-readable. 'json' returns structured data "
                            "with numeric orb, applying, days_to_exact and exact_utc fields."
                        )
                    }
                },
                "required": ["chart1_date", "chart2_date"]
            }
        ),
        Tool(
            name="find_house_placements",
            description=(
                "Determine which house each planet occupies in a chart. "
                "Can use a natal chart (via profile_id or owner default) or a connection chart "
                "(composite/Davison via connection_id + chart_type) as the house reference frame. "
                "Shows both which planets are in each house and which house each planet is in."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date for the planets to place (YYYY-MM-DD), 'natal' for birth chart planets, or 'today' for current sky"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM format, interpreted as UT (optional, defaults to 12:00)"
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID whose natal houses to use as the reference frame (from list_profiles). Defaults to owner profile. Mutually exclusive with connection_id."
                    },
                    "connection_id": {
                        "type": "integer",
                        "description": "Connection ID whose composite/Davison houses to use as the reference frame (from list_connections). Requires chart_type. Mutually exclusive with profile_id."
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["composite", "davison"],
                        "description": "Which connection chart to use as the house reference frame. Required when connection_id is supplied."
                    }
                },
                "required": ["date"]
            }
        ),

        Tool(
            name="visualize_placement_dials",
            description=(
                "Create an interactive page for learning what a planet, a sign and a house mean, "
                "alone and together. Three dials (planet, sign, house) can be turned or switched "
                "off, and the reading shows each layer by itself and how the layers combine. "
                "The chart's own placements and house cusps are loaded as quick picks. "
                "Saves one HTML file to open in a browser."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Where to save the page: a file path, or a file path ending in .html or .htm, or a folder (the file is then named placement_dials_<profile name>.html). Defaults to ~/Downloads/placement_dials_<profile name>.html (for example placement_dials_todd.html). Existing files are overwritten."
                    },
                    "title": {
                        "type": "string",
                        "description": "Heading above the placement quick picks (optional, defaults to 'Natal placements')"
                    },
                    "open_in_browser": {
                        "type": "boolean",
                        "description": "Open the page in the default browser after saving. Defaults to false; ask the user before turning it on."
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to use (from list_profiles). Defaults to owner profile."
                    }
                }
            }
        )
    ]


# ============================================================================
# Shared helpers
# ============================================================================

def get_natal_chart_data(ctx: ToolContext, profile_id: Optional[int] = None):
    """
    Get natal chart for a profile, calculating and caching on demand.

    If profile_id is supplied, uses that profile. Otherwise falls back to
    the owner profile. Raises if neither is configured.

    If the profile has no cached natal data (e.g. newly created profiles or
    existing profiles migrated from v0.8), the chart is calculated via
    EphemerisEngine and saved to the database before returning.
    """
    db = ctx.db

    if profile_id is not None:
        profile = db.get_profile_by_id(profile_id)
        if not profile:
            raise EphemerisError(profile_not_found(profile_id))
    else:
        profile = db.get_owner_profile()
        if not profile:
            raise EphemerisError("Owner profile not configured. Run setup_owner first.")

    chart = db.get_natal_chart_data(profile)

    # Auto-calculate if cache is empty (new profile or pre-v0.9 migration)
    if not chart["planets"]:
        birth_loc = db.get_location_by_id(profile.birth_location_id)
        if not birth_loc:
            raise EphemerisError(
                f"Birth location not found for profile '{profile.name}'. "
                "Cannot calculate natal chart."
            )

        # birth_time is the local time on the birth record; the ephemeris needs UT.
        try:
            ut_date, ut_time = utc_engine_args(
                profile.birth_date, profile.birth_time, birth_loc.timezone
            )
        except TimezoneError as e:
            raise EphemerisError(
                f"Cannot calculate natal chart for '{profile.name}': {e}"
            ) from e

        engine = ctx.engine
        calculated = engine.get_chart(
            birth_loc.latitude,
            birth_loc.longitude,
            ut_date,
            ut_time,
            "P",  # Placidus; matches preferred_house_system_id=1
        )

        house_system_id = profile.preferred_house_system_id or 1
        db.save_natal_chart(profile, calculated, house_system_id)

        # Re-read from DB so format is consistent
        chart = db.get_natal_chart_data(profile)

    return chart


def get_chart_for_date(ctx: ToolContext, date_str, time_str="12:00", location=None, profile_id: Optional[int] = None):
    """Get chart for specific date at a location."""
    engine = ctx.engine
    db = ctx.db

    # Get location
    if location is None:
        if profile_id is not None:
            profile = db.get_profile_by_id(profile_id)
            if not profile:
                raise EphemerisError(profile_not_found(profile_id))
        else:
            profile = db.get_owner_profile()
            if not profile:
                raise EphemerisError("Owner profile not configured. Run setup_owner first.")
        location = db.get_current_home_location(profile)
        if not location:
            raise EphemerisError("No current home location found")

    return engine.get_chart(
        latitude=location.latitude,
        longitude=location.longitude,
        date_str=date_str,
        time_str=time_str,
        house_system_code='P'  # TODO: Get from profile
    )


# ============================================================================
# Handlers
# ============================================================================

async def handle_get_natal_chart(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    try:
        profile_id = arguments.get("profile_id")
        result = get_natal_chart_data(ctx, profile_id=profile_id)
        
        # Format response
        response = f"# Natal Chart for {result['metadata']['date']} at {result['metadata']['time']}\n"
        response += f"Location: {result['metadata']['latitude']}, {result['metadata']['longitude']}\n"
        response += f"House System: {result['metadata']['house_system']}\n\n"
        
        response += "## Planetary Positions\n"
        for planet_name, data in result['planets'].items():
            response += f"- **{planet_name}**: {data['formatted']}\n"
        
        response += "\n## House Cusps\n"
        for house_num in sorted(result['houses'].keys(), key=lambda x: int(x)):
            data = result['houses'][house_num]
            response += f"- House {house_num}: {data['formatted']}\n"
        
        if result['points']:
            response += "\n## Angles\n"
            for point, data in result['points'].items():
                response += f"- **{point}**: {data['formatted']}\n"
        
        return [TextContent(type="text", text=response)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def handle_visualize_natal_chart(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    try:
        profile_id = arguments.get("profile_id")
        natal_chart = get_natal_chart_data(ctx, profile_id=profile_id)
        
        # Get output path
        output_path = arguments.get("output_path", "natal_chart.png")
        chart_title = arguments.get("title", "Natal Chart")
        
        # Create visualization
        saved_path = create_natal_chart(
            planets=natal_chart["planets"],
            houses=natal_chart["houses"],
            points=natal_chart["points"],
            chart_title=chart_title,
            output_path=output_path
        )
        
        return [TextContent(
            type="text",
            text=f"Natal chart visualization created successfully!\n\nSaved to: {saved_path}\n\nThe chart shows:\n- Zodiac wheel with all 12 signs\n- Your 12 houses (Placidus system)\n- All 10 planets positioned by degree\n- Ascendant (red line) and MC (blue line)\n\nYou can now view or share this image."
        )]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating visualization: {e}")]


async def handle_find_house_placements(ctx: ToolContext, arguments: dict) -> list[TextContent]:
    """Handle find_house_placements tool call. Extracted for testability."""
    try:
        date = arguments["date"]
        time = arguments.get("time", "12:00")
        profile_id = arguments.get("profile_id")
        connection_id = arguments.get("connection_id")
        chart_type = arguments.get("chart_type")
        db = ctx.db

        # connection_id and profile_id are mutually exclusive
        if connection_id is not None and profile_id is not None:
            return [TextContent(
                type="text",
                text="Error: connection_id and profile_id are mutually exclusive. "
                     "Supply one or the other, not both."
            )]

        if connection_id is not None:
            # --- Connection chart as house reference frame ---
            if not chart_type:
                return [TextContent(
                    type="text",
                    text="Error: chart_type ('composite' or 'davison') is required when connection_id is supplied."
                )]

            connection = db.get_connection_by_id(connection_id)
            if not connection:
                return [TextContent(type="text", text=f"Error: connection {connection_id} not found.")]

            cached = db.get_connection_chart(connection_id, chart_type)
            if not cached or not cached.is_valid:
                return [TextContent(
                    type="text",
                    text=f"Error: no valid {chart_type} chart for connection {connection_id}. "
                         "Run get_connection_chart first."
                )]

            raw_houses = db.get_connection_houses(cached.id)
            if not raw_houses:
                return [TextContent(type="text", text=f"Error: no house data for {chart_type} chart.")]

            houses = {
                str(h.house_number): {
                    "degree": h.degree + (h.minutes or 0) / 60.0,
                    "sign": h.sign,
                }
                for h in raw_houses
            }
            reference_label = f"{connection.label} ({chart_type.title()})"

            if date == "natal":
                return [TextContent(
                    type="text",
                    text="Error: 'natal' date is ambiguous with a connection_id. "
                         "Supply a specific date or 'today'."
                )]
            transit_chart = get_chart_for_date(ctx, None if date == "today" else date, time)
            planets = transit_chart["planets"]

        else:
            # --- Natal chart as house reference frame ---
            if date == "natal":
                # Natal planets in natal houses
                chart = get_natal_chart_data(ctx, profile_id=profile_id)
                planets = chart["planets"]
                houses = chart["houses"]
            else:
                # Transit planets placed against the profile's natal houses
                transit_chart = get_chart_for_date(ctx, None if date == "today" else date, time)
                natal = get_natal_chart_data(ctx, profile_id=profile_id)
                planets = transit_chart["planets"]
                houses = natal["houses"]
            reference_label = None

        result = find_planets_in_houses(planets, houses)
        report = format_house_report(result)
        if reference_label:
            report = report.replace(
                "# House Placements",
                f"# House Placements \u2014 {reference_label}"
            )
        return [TextContent(type="text", text=report)]

    except AnalysisError as e:
        return [TextContent(type="text", text=f"Analysis error: {e}")]
    except EphemerisError as e:
        return [TextContent(type="text", text=f"Ephemeris error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


class _ChartNotFound(Exception):
    """A referenced chart (e.g. a saved event chart) does not exist."""


def _profile_name(db, profile_id: Optional[int]) -> Optional[str]:
    """Best-effort profile name for chart labels (owner profile when no id is given)."""
    try:
        profile = db.get_profile_by_id(profile_id) if profile_id is not None else db.get_owner_profile()
    except Exception:  # labels are cosmetic; never fail a comparison over one
        return None
    name = getattr(profile, "name", None)
    return name if isinstance(name, str) else None


async def handle_compare_charts(ctx: ToolContext, arguments: dict) -> list[TextContent]:
    """Handle compare_charts tool call. Extracted for testability."""
    try:
        output_format = arguments.get("format", "text")
        if output_format not in ("text", "json"):
            return [TextContent(type="text", text="Error: format must be 'text' or 'json'.")]

        include_angles = arguments.get("include_angles")
        if include_angles is not None and include_angles not in INCLUDE_ANGLES_MODES:
            return [TextContent(
                type="text",
                text="Error: include_angles must be one of: " + ", ".join(INCLUDE_ANGLES_MODES) + ".",
            )]

        # chart retrieval goes through get_chart_for_date, which uses the context's engine
        db = ctx.db

        def resolve_chart(prefix: str):
            """Return (chart, meta) for chart1 / chart2. meta feeds labels and include_angles."""
            date = arguments[f"{prefix}_date"]
            time = arguments.get(f"{prefix}_time", "12:00")
            profile_id = arguments.get(f"{prefix}_profile_id")

            if date == "natal":
                return (
                    get_natal_chart_data(ctx, profile_id=profile_id),
                    {"kind": "natal", "profile_id": profile_id},
                )
            if date == "today":
                return get_chart_for_date(ctx, None, time), {"kind": "transit"}
            if date.startswith("event:"):
                label = date[len("event:"):]
                ev = db.get_event_chart_by_label(label)
                if not ev:
                    raise _ChartNotFound(f"no saved event chart with label '{label}'")
                return db.get_event_chart_positions(ev.id), {"kind": f"event:{label}"}
            return get_chart_for_date(ctx, date, time), {"kind": "transit"}

        chart1, meta1 = resolve_chart("chart1")
        chart2, meta2 = resolve_chart("chart2")

        # Profile names only matter when both charts are natal (synastry) and would
        # otherwise carry identical labels.
        if meta1["kind"] == "natal" and meta2["kind"] == "natal":
            meta1["name"] = _profile_name(db, meta1.get("profile_id"))
            meta2["name"] = _profile_name(db, meta2.get("profile_id"))

        result = compare_charts(
            chart1,
            chart2,
            orb_multiplier=arguments.get("orb_multiplier", 1.0),
            planets_only=arguments.get("planets_only", True),
            include_angles=include_angles,
            chart1_meta=meta1,
            chart2_meta=meta2,
        )

        report = format_aspect_json(result) if output_format == "json" else format_aspect_report(result)
        return [TextContent(type="text", text=report)]

    except _ChartNotFound as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except AnalysisError as e:
        return [TextContent(type="text", text=f"Analysis error: {e}")]
    except EphemerisError as e:
        return [TextContent(type="text", text=f"Ephemeris error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def get_profile_info(ctx: ToolContext, profile_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Name, id and birth time of the given profile (the owner's when None), and whether
    another profile has the same name. Returns {} if it can't be found, so callers can
    carry on without it.
    """
    try:
        db = ctx.db
        profile = db.get_profile_by_id(profile_id) if profile_id is not None else db.get_owner_profile()
        if not profile:
            return {}
        same_name = [
            p for p in db.list_all_profiles()
            if p.id != profile.id and placement_dials_slug(p.name) == placement_dials_slug(profile.name)
        ]
        return {
            "id": profile.id,
            "name": profile.name,
            "birth_time": profile.birth_time,
            "name_shared": bool(same_name),
        }
    except Exception as e:
        logger.warning("Could not look up the profile for placement dials: %s", e)
        return {}


def _placement_dials_notices(info: Dict[str, Any]) -> list:
    """Caveats shown on the page under the quick picks."""
    notices = []
    if info.get("birth_time") == "12:00":
        notices.append(
            "This profile's birth time is 12:00, which is often a placeholder for an unknown time. "
            "If it is a guess, the houses and the Moon's degree are not reliable. Planet and sign "
            "meanings are unaffected."
        )
    return notices


async def handle_visualize_placement_dials(ctx: ToolContext, arguments: dict) -> list[TextContent]:
    """Save the placement-dials page for a profile's natal chart."""
    try:
        chart = get_natal_chart_data(ctx, profile_id=arguments.get("profile_id"))
        info = get_profile_info(ctx, arguments.get("profile_id"))
        # Two profiles with the same name get their ids in the file name so they don't collide.
        file_label = f"{info['name']} {info['id']}" if info.get("name_shared") else info.get("name")
        saved_path = create_placement_dials(
            chart,
            title=arguments.get("title") or PLACEMENT_DIALS_TITLE,
            output_path=arguments.get("output_path") or None,
            profile_name=file_label,
            profile_id=info.get("id", arguments.get("profile_id")),
            notices=_placement_dials_notices(info),
        )
        how_to_use = (
            "Turn the planet, sign and house dials, or switch a layer off to read it alone. "
            "The chart's ten placements are quick picks, and the house toggle switches between "
            "this chart's house cusps and the textbook scheme."
        )
        if arguments.get("open_in_browser"):
            if open_in_default_browser(saved_path):
                status = "Opened in your default browser."
            else:
                status = "Could not open a browser from here, so open the file yourself."
            text = f"Placement dials created.\n\nSaved to: {saved_path}\n\n{status} {how_to_use}"
        else:
            text = f"Placement dials created.\n\nSaved to: {saved_path}\n\nOpen it in a browser. {how_to_use}"
        return [TextContent(type="text", text=text)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


# ============================================================================
# Registration
# ============================================================================

def tool_specs() -> list[ToolSpec]:
    """The chart tools. All five read stored natal charts, so each can carry a data notice."""
    return bind_handlers(
        get_chart_tools(),
        {
            "get_natal_chart": handle_get_natal_chart,
            "visualize_natal_chart": handle_visualize_natal_chart,
            "compare_charts": handle_compare_charts,
            "find_house_placements": handle_find_house_placements,
            "visualize_placement_dials": handle_visualize_placement_dials,
        },
        natal_chart_tools=frozenset(
            {
                "get_natal_chart", "visualize_natal_chart", "compare_charts", "find_house_placements",
                "visualize_placement_dials",
            }
        ),
    )
