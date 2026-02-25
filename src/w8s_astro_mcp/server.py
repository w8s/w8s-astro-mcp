"""MCP server for w8s-astro-mcp."""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

import os
import urllib.request
from pathlib import Path

from .utils.ephemeris import EphemerisEngine, EphemerisError
from .utils.db_helpers import DatabaseHelper
from .utils.geocoding import geocode_location
from .tools.analysis_tools import (
    compare_charts,
    find_planets_in_houses,
    format_aspect_report,
    format_house_report,
    AnalysisError
)
from .tools.visualization import create_natal_chart
from .tools.profile_management import (
    get_profile_management_tools,
    handle_profile_tool
)
from .tools.connection_management import (
    get_connection_tools,
    handle_connection_tool,
    CONNECTION_TOOL_NAMES,
)
from .tools.event_management import (
    get_event_tools,
    handle_event_tool,
    EVENT_TOOL_NAMES,
)


# Initialize MCP server
app = Server("w8s-astro-mcp")

# Global state
db_helper: Optional[DatabaseHelper] = None
ephemeris: Optional[EphemerisEngine] = None


def init_db():
    """Initialize database helper."""
    global db_helper
    if db_helper is None:
        db_helper = DatabaseHelper()
    return db_helper


def init_ephemeris() -> EphemerisEngine:
    """Initialize the ephemeris engine (lazy singleton)."""
    global ephemeris
    if ephemeris is None:
        # Honour an optional env-var override for the .se1 file directory.
        ephe_path = os.environ.get("SE_EPHE_PATH") or None
        ephemeris = EphemerisEngine(ephe_path=ephe_path)
    return ephemeris


def get_natal_chart_data():
    """
    Get natal chart for the current profile, calculating and caching on demand.

    If the profile has no cached natal data (e.g. newly created profiles or
    existing profiles migrated from v0.8), the chart is calculated via
    EphemerisEngine and saved to the database before returning.
    """
    db = init_db()

    profile = db.get_current_profile()
    if not profile:
        raise EphemerisError("No primary profile found. Run migration script first.")

    chart = db.get_natal_chart_data(profile)

    # Auto-calculate if cache is empty (new profile or pre-v0.9 migration)
    if not chart["planets"]:
        birth_loc = db.get_location_by_id(profile.birth_location_id)
        if not birth_loc:
            raise EphemerisError(
                f"Birth location not found for profile '{profile.name}'. "
                "Cannot calculate natal chart."
            )

        engine = init_ephemeris()
        calculated = engine.get_chart(
            birth_loc.latitude,
            birth_loc.longitude,
            profile.birth_date,
            profile.birth_time,
            "P",  # Placidus; matches preferred_house_system_id=1
        )

        house_system_id = profile.preferred_house_system_id or 1
        db.save_natal_chart(profile, calculated, house_system_id)

        # Re-read from DB so format is consistent
        chart = db.get_natal_chart_data(profile)

    return chart


def get_chart_for_date(date_str, time_str="12:00", location=None):
    """Get chart for specific date at a location."""
    engine = init_ephemeris()
    db = init_db()

    # Get location
    if location is None:
        profile = db.get_current_profile()
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


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    # Core tools
    core_tools = [
        Tool(
            name="check_ephemeris",
            description=(
                "Check the current ephemeris mode and precision level. "
                "Reports whether the built-in Moshier ephemeris (~1 arcminute) or "
                "Swiss Ephemeris data files (~0.001 arcsecond) are active, "
                "and shows the pysweph version."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="download_ephemeris_files",
            description=(
                "Download Swiss Ephemeris data files for higher-precision calculations. "
                "Upgrades from built-in Moshier ephemeris (~1 arcminute) to full Swiss Ephemeris "
                "files (~0.001 arcsecond). Downloads ~2 MB from the official Swiss Ephemeris "
                "GitHub repository to ~/.w8s-astro-mcp/ephe/. "
                "Use check_ephemeris first to see current precision mode."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "confirm": {
                        "type": "boolean",
                        "description": (
                            "Must be true to proceed. Omit or set false to preview "
                            "file details (names, sizes, source, destination) first."
                        )
                    }
                }
            }
        ),
        Tool(
            name="setup_astro_config",
            description=(
                "Configure birth data and location for transit calculations. "
                "IMPORTANT: Ask the user for information conversationally in steps:\n"
                "1. Ask: 'What's your birthday?' (get YYYY-MM-DD)\n"
                "2. Ask: 'Do you know what time you were born? (If not, we can use 12:00)' (get HH:MM)\n"
                "3. Ask: 'Where were you born?' (get city, state/country)\n"
                "Then look up coordinates and confirm with user before saving."
            ),
            inputSchema={
                "type": "object",
                "properties": {
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
                        "description": "Location name (e.g., 'Richardson, TX')"
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
                        "description": "Timezone (e.g., 'America/Chicago')"
                    }
                },
                "required": ["birth_date", "birth_time", "birth_location_name", 
                           "birth_latitude", "birth_longitude", "birth_timezone"]
            }
        ),
        Tool(
            name="view_config",
            description="View current astrological configuration (birth data and saved locations)",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="get_natal_chart",
            description="Get the natal chart (birth chart) planetary positions for the configured birth data",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="get_transits",
            description=(
                "Get planetary transits for a specific date and location. "
                "Location can be a saved label ('home', 'work', 'birth'), "
                "or any city/place name ('Seattle', 'Bangkok, Thailand', 'Paris') — "
                "unknown names are geocoded automatically. "
                "Defaults to current home location if omitted."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (optional, defaults to today)"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM format (optional, defaults to 12:00)"
                    },
                    "location": {
                        "type": "string",
                        "description": (
                            "Saved label ('home', 'work', 'birth') or any city name "
                            "('Bangkok, Thailand', 'Seattle, WA'). Defaults to 'current'."
                        )
                    }
                }
            }
        ),
        Tool(
            name="get_transit_history",
            description=(
                "Query historical transit lookups stored in the database for the current profile. "
                "Supports filtering by date range, planet, and sign. "
                "Examples: 'show me last month\\'s transits', "
                "'when was Mercury in Capricorn?', 'what sign was Jupiter in last year?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "after": {
                        "type": "string",
                        "description": "Return lookups on or after this date (YYYY-MM-DD, optional)"
                    },
                    "before": {
                        "type": "string",
                        "description": "Return lookups on or before this date (YYYY-MM-DD, optional)"
                    },
                    "planet": {
                        "type": "string",
                        "description": "Filter by planet name, e.g. 'Mercury' (optional)"
                    },
                    "sign": {
                        "type": "string",
                        "description": "Filter by zodiac sign, e.g. 'Capricorn' — requires planet (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of results to return (default 20, max 100)"
                    }
                }
            }
        ),
        Tool(
            name="find_last_transit",
            description=(
                "Find the most recent logged transit where a planet met specific conditions. "
                "Examples: 'when was Mercury last retrograde?', "
                "'when was the Moon last in Scorpio?', "
                "'when was Mars last in my 7th house?'. "
                "Requires at least one of: sign, retrograde, or house."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "planet": {
                        "type": "string",
                        "description": "Planet name, e.g. 'Mercury', 'Mars'"
                    },
                    "sign": {
                        "type": "string",
                        "description": "Zodiac sign to match, e.g. 'Capricorn' (optional)"
                    },
                    "retrograde": {
                        "type": "boolean",
                        "description": "If true, find last retrograde; if false, find last direct (optional)"
                    },
                    "house": {
                        "type": "integer",
                        "description": "Natal house number to match, 1-12 (optional)"
                    }
                },
                "required": ["planet"]
            }
        ),
        Tool(
            name="get_ingresses",
            description=(
                "Scan the ephemeris for upcoming or recent planetary sign ingresses "
                "and stations (retrograde/direct). "
                "Examples: 'what transits are coming up this month?', "
                "'when does Mercury go retrograde?', "
                "'show me major transits next April', "
                "'what were the outer planet movements during the Renaissance?'. "
                "Use offset to shift the window from today. "
                "Use extended=true for historical or far-future windows (outer planets only)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": (
                            "Number of days to scan. "
                            "Normal mode: default 30, max 365. "
                            "Extended mode: default 30, max 3650."
                        )
                    },
                    "future": {
                        "type": "boolean",
                        "description": "True = scan forward from today+offset (default), False = backward"
                    },
                    "offset": {
                        "type": "integer",
                        "description": (
                            "Days from today to start the scan window (default 0). "
                            "Normal mode: max 36500 (~100 years). "
                            "Extended mode: uncapped."
                        )
                    },
                    "extended": {
                        "type": "boolean",
                        "description": (
                            "If true, removes offset cap and raises scan cap to 3650 days, "
                            "but only returns outer planets (Jupiter through Pluto). "
                            "Inner planets are excluded in extended mode — they produce "
                            "thousands of events over long windows and become unreadable. "
                            "See docs/ARCHITECTURE.md for rationale and how to request changes."
                        )
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
                "Finds conjunctions, oppositions, trines, squares, sextiles, and minor aspects."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chart1_date": {
                        "type": "string",
                        "description": "Date for first chart (YYYY-MM-DD), use 'natal' for configured birth chart, or 'event:<label>' for a saved event chart"
                    },
                    "chart1_time": {
                        "type": "string",
                        "description": "Time for first chart in HH:MM format (optional, defaults to 12:00)"
                    },
                    "chart2_date": {
                        "type": "string",
                        "description": "Date for second chart (YYYY-MM-DD), use 'natal' for birth chart, 'today' for current, or 'event:<label>' for a saved event chart"
                    },
                    "chart2_time": {
                        "type": "string",
                        "description": "Time for second chart in HH:MM format (optional, defaults to 12:00)"
                    },
                    "orb_multiplier": {
                        "type": "number",
                        "description": "Multiplier for aspect orbs (optional, default 1.0)"
                    },
                    "planets_only": {
                        "type": "boolean",
                        "description": "If true, only compare planets, not angles/points (optional, default true)"
                    }
                },
                "required": ["chart1_date", "chart2_date"]
            }
        ),
        Tool(
            name="find_house_placements",
            description="Determine which house each planet occupies in a chart. Shows both which planets are in each house and which house each planet is in.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date for chart (YYYY-MM-DD), use 'natal' for configured birth chart or 'today' for current"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM format (optional, defaults to 12:00)"
                    }
                },
                "required": ["date"]
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
                    }
                }
            }
        )
    ]
    
    # Add profile management tools
    profile_tools = get_profile_management_tools()

    # Add connection management tools (Phase 7)
    connection_tools = get_connection_tools()

    # Add event chart tools (Phase 8)
    event_tools = get_event_tools()

    return core_tools + profile_tools + connection_tools + event_tools



@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "check_ephemeris":
        import swisseph as swe
        engine = init_ephemeris()
        mode = engine.get_mode()
        ephe_dir = Path.home() / ".w8s-astro-mcp" / "ephe"
        files = list(ephe_dir.glob("*.se1")) if ephe_dir.exists() else []

        lines = [
            f"Ephemeris mode: {mode}",
            f"pysweph version: {swe.__version__}",
        ]
        if mode == "moshier":
            lines.append("Precision: ~1 arcminute (Moshier built-in, no files needed)")
            lines.append("Use download_ephemeris_files to upgrade to ~0.001 arcsecond precision.")
        else:
            lines.append(f"Precision: ~0.001 arcsecond (Swiss Ephemeris files)")
            lines.append(f"Ephemeris path: {engine.ephe_path}")
            if files:
                lines.append(f"Data files: {', '.join(f.name for f in sorted(files))}")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "download_ephemeris_files":
        ephe_dir = Path.home() / ".w8s-astro-mcp" / "ephe"
        file_manifest = [
            ("sepl_18.se1", "Planets (Sun–Pluto), 1800–2400 CE",  "473 KB"),
            ("semo_18.se1", "Moon, 1800–2400 CE",                  "1.3 MB"),
            ("seas_18.se1", "Main asteroids, 1800–2400 CE",        "218 KB"),
        ]
        base_url = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe"

        confirm = arguments.get("confirm", False)

        if not confirm:
            # Show manifest; require explicit confirmation before downloading.
            lines = [
                "Swiss Ephemeris data files upgrade",
                "",
                f"Current mode: {init_ephemeris().get_mode()}",
                "After upgrade: Swiss Ephemeris (~0.001 arcsecond precision)",
                "",
                "Files to download:",
            ]
            for fname, desc, size in file_manifest:
                lines.append(f"  {fname:<16} {desc:<40} {size}")
            lines += [
                f"  Total                                                    ~2.0 MB",
                "",
                f"Source:      github.com/aloistr/swisseph (official Swiss Ephemeris repository)",
                f"Destination: {ephe_dir}",
                "",
                "Call again with confirm=true to proceed.",
            ]
            return [TextContent(type="text", text="\n".join(lines))]

        # Check which files are already present.
        ephe_dir.mkdir(parents=True, exist_ok=True)
        lines = ["Downloading Swiss Ephemeris data files...", ""]
        all_present = True
        for fname, _desc, _size in file_manifest:
            dest = ephe_dir / fname
            if dest.exists():
                lines.append(f"  ✓ {fname}  already present — skipped")
            else:
                all_present = False
                url = f"{base_url}/{fname}"
                try:
                    urllib.request.urlretrieve(url, dest)
                    size_kb = dest.stat().st_size // 1024
                    lines.append(f"  ✓ {fname}  {size_kb} KB   saved to {ephe_dir}")
                except Exception as exc:
                    lines.append(f"  ✗ {fname}  FAILED: {exc}")

        # Activate the downloaded files immediately (no restart needed).
        global ephemeris
        ephemeris = EphemerisEngine(ephe_path=str(ephe_dir))

        lines += ["", "High-precision mode active. No restart required."]
        return [TextContent(type="text", text="\n".join(lines))]
    
    elif name == "setup_astro_config":
        return [TextContent(
            type="text",
            text="⚠️ This tool is deprecated.\n\n"
                 "The w8s-astro-mcp now uses SQLite database instead of config.json.\n\n"
                 "Your data has been migrated to: ~/.w8s-astro-mcp/astro.db\n\n"
                 "To add new profiles or locations, use the database migration script or "
                 "contact the developer for profile management tools."
        )]
    
    elif name == "view_config":
        try:
            db = init_db()
            
            response = "# Current Configuration\n\n"
            
            # Primary profile
            profile = db.get_current_profile()
            if profile:
                birth_loc = db.get_birth_location(profile)
                response += "## Primary Profile\n"
                response += f"Name: {profile.name}\n"
                response += f"Birth Date: {profile.birth_date}\n"
                response += f"Birth Time: {profile.birth_time}\n"
                if birth_loc:
                    response += f"Birth Location: {birth_loc.label}\n"
                    response += f"Coordinates: {birth_loc.latitude}, {birth_loc.longitude}\n"
                    response += f"Timezone: {birth_loc.timezone}\n"
                response += "\n"
            else:
                response += "## Primary Profile\nNot configured.\n\n"
            
            # Locations
            if profile:
                locations = db.list_all_locations(profile)
                if locations:
                    response += "## Saved Locations\n"
                    for loc in locations:
                        marker = " (current home)" if loc.is_current_home else ""
                        response += f"- {loc.label}{marker}: {loc.latitude}, {loc.longitude}\n"
                    response += "\n"
            
            response += f"Database: {db.engine.url.database}\n"
            
            return [TextContent(type="text", text=response)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "get_natal_chart":
        try:
            # Get natal chart data from database
            result = get_natal_chart_data()
            
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

    elif name == "get_transit_history":
        try:
            db = init_db()
            profile = db.get_current_profile()
            if not profile:
                return [TextContent(type="text", text="Error: No profile configured.")]

            after = arguments.get("after")
            before = arguments.get("before")
            planet = arguments.get("planet")
            sign = arguments.get("sign")
            limit = min(int(arguments.get("limit", 20)), 100)

            rows = db.get_transit_history(
                profile,
                after=after,
                before=before,
                planet=planet,
                sign=sign,
                limit=limit,
            )

            if not rows:
                filters = []
                if after:
                    filters.append(f"after {after}")
                if before:
                    filters.append(f"before {before}")
                if planet:
                    filters.append(f"planet={planet}")
                if sign:
                    filters.append(f"sign={sign}")
                filter_str = ", ".join(filters) if filters else "no filters"
                return [TextContent(
                    type="text",
                    text=f"No transit history found for {profile.name} ({filter_str})."
                )]

            # Format response
            response = f"# Transit History — {profile.name}\n"
            if after or before:
                date_range = f"{after or '...'} → {before or 'now'}"
                response += f"Date range: {date_range}\n"
            if planet:
                response += f"Planet filter: {planet}"
                if sign:
                    response += f" in {sign}"
                response += "\n"
            response += f"Showing {len(rows)} lookup(s), newest first\n\n"

            PLANET_ORDER = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

            for row in rows:
                dt = row["lookup_datetime"].replace("T", " ")[:16]
                response += f"## {dt}  —  {row['location_label']}\n"

                planets_to_show = (
                    {planet: row["planets"][planet]}
                    if planet and planet in row["planets"]
                    else row["planets"]
                )

                for pname in PLANET_ORDER:
                    if pname not in planets_to_show:
                        continue
                    pdata = planets_to_show[pname]
                    retro = " ℞" if pdata.get("is_retrograde") else ""
                    response += (
                        f"  {pname}: {pdata['degree']:.1f}° {pdata['sign']}{retro}\n"
                    )
                response += "\n"

            return [TextContent(type="text", text=response)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "find_last_transit":
        try:
            db = init_db()
            profile = db.get_current_profile()
            if not profile:
                return [TextContent(type="text", text="Error: No profile configured.")]

            planet = arguments.get("planet")
            if not planet:
                return [TextContent(type="text", text="Error: 'planet' is required.")]

            sign = arguments.get("sign")
            retrograde = arguments.get("retrograde")  # None / True / False
            house = arguments.get("house")
            if house is not None:
                house = int(house)

            if sign is None and retrograde is None and house is None:
                return [TextContent(
                    type="text",
                    text="Error: Provide at least one filter: sign, retrograde, or house."
                )]

            result = db.find_last_transit(
                profile,
                planet=planet,
                sign=sign,
                retrograde=retrograde,
                house=house,
            )

            if result is None:
                conditions = []
                if sign:
                    conditions.append(f"in {sign}")
                if retrograde is True:
                    conditions.append("retrograde")
                elif retrograde is False:
                    conditions.append("direct")
                if house:
                    conditions.append(f"in house {house}")
                cond_str = " and ".join(conditions)
                return [TextContent(
                    type="text",
                    text=f"No logged transit found for {planet} {cond_str} in {profile.name}'s history."
                )]

            dt = result["lookup_datetime"].replace("T", " ")[:16]
            retro_str = " ℞ (retrograde)" if result["is_retrograde"] else ""
            house_str = f", House {result['house_number']}" if result["house_number"] else ""

            conditions = []
            if sign:
                conditions.append(f"in {sign}")
            if retrograde is True:
                conditions.append("retrograde")
            elif retrograde is False:
                conditions.append("direct")
            if house:
                conditions.append(f"in house {house}")
            cond_str = " and ".join(conditions)

            response = (
                f"# Last {planet} {cond_str}\n\n"
                f"**{dt}** — {result['location_label']}\n"
                f"{planet}: {result['degree']:.1f}° {result['sign']}{retro_str}{house_str}\n"
            )
            return [TextContent(type="text", text=response)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "get_ingresses":
        try:
            ephem_engine = init_ephemeris()
            db = init_db()
            profile = db.get_current_profile()
            if not profile:
                return [TextContent(type="text", text="Error: No profile configured.")]

            extended = bool(arguments.get("extended", False))
            days = int(arguments.get("days", 30))
            future = arguments.get("future", True)
            offset = int(arguments.get("offset", 0))

            events = db.get_ingresses(
                profile, ephem_engine,
                days=days, future=future,
                offset=offset, extended=extended,
            )

            direction_word = "Upcoming" if future else "Recent"
            offset_note = f", starting {offset} days from today" if offset else ""
            ext_note = " _(extended mode — outer planets only)_" if extended else ""
            response = (
                f"# {direction_word} Ingresses & Stations"
                f" — {days} days{offset_note}{ext_note}\n\n"
            )

            if not events:
                response += "No ingresses or stations found in this period.\n"
                return [TextContent(type="text", text=response)]

            # Group by month for readability
            from datetime import date
            current_month = None
            for event in events:
                month = event["date"][:7]  # YYYY-MM
                if month != current_month:
                    d = date.fromisoformat(event["date"])
                    response += f"## {d.strftime('%B %Y')}\n"
                    current_month = month

                d = date.fromisoformat(event["date"])
                day_str = d.strftime("%b %-d")

                if event["event_type"] == "ingress":
                    response += (
                        f"**{day_str}** — {event['planet']} {event['detail']} "
                        f"(from {event['from_sign']})\n"
                    )
                else:  # station
                    retro_symbol = " ℞" if event["is_retrograde"] else " D"
                    response += (
                        f"**{day_str}** — {event['planet']}{retro_symbol} "
                        f"{event['detail']} in {event['sign']}\n"
                    )

            response += f"\n_{len(events)} event(s) total_\n"
            return [TextContent(type="text", text=response)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    elif name == "get_transits":
        try:
            engine = init_ephemeris()
            db = init_db()
            
            date_str = arguments.get("date")
            time_str = arguments.get("time", "12:00")
            location_arg = arguments.get("location", "current")
            
            # Get profile
            profile = db.get_current_profile()
            if not profile:
                return [TextContent(type="text", text="No primary profile found")]
            
            # Resolve location
            #
            # Priority:
            #   1. Special keywords: current/home → current home location
            #   2. 'birth' → birth location
            #   3. Saved label match (case-insensitive)
            #   4. Geocode as an arbitrary city/place name (not saved)
            #
            # Ad-hoc geocoded locations are used for the ephemeris call but
            # never persisted — they won't appear in transit history location
            # labels unless the user explicitly saves them with add_location.

            location = None          # SQLAlchemy Location object (saved)
            adhoc_location = None    # dict for one-off geocoded locations

            if location_arg in ("current", "home"):
                location = db.get_current_home_location(profile)
                if not location:
                    return [TextContent(type="text", text="No current home location set")]
            elif location_arg == "birth":
                location = db.get_birth_location(profile)
            else:
                # Try saved label first
                location = db.get_location_by_label(location_arg, profile)
                if not location:
                    # Fall back to geocoding
                    geo = geocode_location(location_arg)
                    if geo:
                        adhoc_location = geo
                    else:
                        return [TextContent(
                            type="text",
                            text=(
                                f"Location '{location_arg}' not found as a saved label "
                                f"and could not be geocoded. Try a more specific name "
                                f"(e.g. 'Bangkok, Thailand' or 'Seattle, WA')."
                            )
                        )]

            # Resolve lat/lon/label for the ephemeris call
            if adhoc_location:
                lat = adhoc_location["latitude"]
                lon = adhoc_location["longitude"]
                location_label = adhoc_location["name"].split(",")[0]  # short display name
            else:
                lat = location.latitude
                lon = location.longitude
                location_label = location.label
            
            # Get transits from ephemeris engine
            result = engine.get_chart(
                latitude=lat,
                longitude=lon,
                date_str=date_str,
                time_str=time_str,
                house_system_code='P'  # TODO: Get from profile
            )

            # AUTO-LOG: Save this transit lookup to database (saved locations only)
            # Ad-hoc geocoded locations are not persisted — log is skipped gracefully.
            try:
                if location:
                    lookup_datetime = datetime.strptime(
                        f"{result['metadata']['date']} {result['metadata']['time']}",
                        "%Y-%m-%d %H:%M:%S"
                    )
                    db.save_transit_lookup(
                        profile=profile,
                        location=location,
                        lookup_datetime=lookup_datetime,
                        transit_data=result,
                        house_system_id=profile.preferred_house_system_id
                    )
            except Exception as log_error:
                # Don't fail the entire request if logging fails
                print(f"Warning: Failed to log transit lookup: {log_error}")

            # Format response
            response = f"Transits for {result['metadata']['date']} at {result['metadata']['time']}\n"
            response += f"Location: {location_label} ({result['metadata']['latitude']}, {result['metadata']['longitude']})\n"
            response += f"House System: {result['metadata']['house_system']}\n\n"
            
            response += "Planets:\n"
            for planet, data in result['planets'].items():
                response += f"  {planet}: {data['degree']:.2f}° {data['sign']}\n"
            
            response += "\nHouses:\n"
            for house_num in sorted(result['houses'].keys(), key=lambda x: int(x)):
                data = result['houses'][house_num]
                response += f"  House {house_num}: {data['degree']:.2f}° {data['sign']}\n"
            
            if result['points']:
                response += "\nSpecial Points:\n"
                for point, data in result['points'].items():
                    response += f"  {point}: {data['degree']:.2f}° {data['sign']}\n"
            
            return [TextContent(type="text", text=response)]
            
        except EphemerisError as e:
            return [TextContent(type="text", text=f"Ephemeris error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "compare_charts":
        try:
            # chart retrieval goes through get_chart_for_date which calls init_ephemeris()
            
            # Get chart1
            chart1_date = arguments["chart1_date"]
            chart1_time = arguments.get("chart1_time", "12:00")
            
            if chart1_date == "natal":
                chart1 = get_natal_chart_data()
            elif chart1_date == "today":
                chart1 = get_chart_for_date(None, chart1_time)
            elif chart1_date.startswith("event:"):
                label = chart1_date[len("event:"):]
                ev = db.get_event_chart_by_label(label)
                if not ev:
                    return [TextContent(type="text", text=f"Error: no saved event chart with label '{label}'")]
                chart1 = db.get_event_chart_positions(ev.id)
            else:
                chart1 = get_chart_for_date(chart1_date, chart1_time)
            
            # Get chart2
            chart2_date = arguments["chart2_date"]
            chart2_time = arguments.get("chart2_time", "12:00")
            
            if chart2_date == "natal":
                chart2 = get_natal_chart_data()
            elif chart2_date == "today":
                chart2 = get_chart_for_date(None, chart2_time)
            elif chart2_date.startswith("event:"):
                label = chart2_date[len("event:"):]
                ev = db.get_event_chart_by_label(label)
                if not ev:
                    return [TextContent(type="text", text=f"Error: no saved event chart with label '{label}'")]
                chart2 = db.get_event_chart_positions(ev.id)
            else:
                chart2 = get_chart_for_date(chart2_date, chart2_time)
            
            # Compare charts
            result = compare_charts(
                chart1,
                chart2,
                orb_multiplier=arguments.get("orb_multiplier", 1.0),
                planets_only=arguments.get("planets_only", True)
            )
            
            # Format and return
            report = format_aspect_report(result)
            return [TextContent(type="text", text=report)]
            
        except AnalysisError as e:
            return [TextContent(type="text", text=f"Analysis error: {e}")]
        except EphemerisError as e:
            return [TextContent(type="text", text=f"Ephemeris error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "find_house_placements":
        try:
            # Get chart
            date = arguments["date"]
            time = arguments.get("time", "12:00")
            
            if date == "natal":
                chart = get_natal_chart_data()
            elif date == "today":
                chart = get_chart_for_date(None, time)
            else:
                chart = get_chart_for_date(date, time)
            
            # Analyze house placements
            result = find_planets_in_houses(
                chart["planets"],
                chart["houses"]
            )
            
            # Format and return
            report = format_house_report(result)
            return [TextContent(type="text", text=report)]
            
        except AnalysisError as e:
            return [TextContent(type="text", text=f"Analysis error: {e}")]
        except EphemerisError as e:
            return [TextContent(type="text", text=f"Ephemeris error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "visualize_natal_chart":
        try:
            # Get natal chart data from database
            natal_chart = get_natal_chart_data()
            
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
    
    # Profile management tools
    elif name in ["list_profiles", "create_profile", "update_profile", "delete_profile",
                  "set_current_profile", "add_location", "remove_location"]:
        db = init_db()
        return await handle_profile_tool(name, arguments, db)

    # Connection management tools (Phase 7)
    elif name in CONNECTION_TOOL_NAMES:
        db = init_db()
        engine = init_ephemeris()
        return await handle_connection_tool(name, arguments, db, engine)

    # Event chart tools (Phase 8)
    elif name in EVENT_TOOL_NAMES:
        db = init_db()
        return await handle_event_tool(name, arguments, db)

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
