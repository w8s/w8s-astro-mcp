"""MCP server for w8s-astro-mcp."""

import asyncio
import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.types import TextContent, Tool

from .registry import ToolContext, ToolRegistry
from .tools import (
    chart_tools,
    connection_management,
    event_management,
    profile_management,
    transit_tools,
)
from .tools.chart_tools import get_natal_chart_data
from .tools.placement_dials import (
    DEFAULT_TITLE as PLACEMENT_DIALS_TITLE,
    create_placement_dials,
    open_in_default_browser,
    slugify as placement_dials_slug,
)
from .utils import chart_health
from .utils.chart_health import DataNoticeGate, data_notice
from .utils.db_helpers import DatabaseHelper
from .utils.ephemeris import EphemerisEngine


# Initialize MCP server
# Durable guidance sent to the AI when it connects. Facts about the user's data belong in tool
# results (see the data notice below), not here.
SERVER_INSTRUCTIONS = (
    "w8s-astro-mcp: astrology charts and transits (Swiss Ephemeris).\n\n"
    "Times: birth times, cast_event_chart times and find_electional_windows dates are LOCAL time at "
    "the location and are converted using its timezone. The `time` argument of get_transits, "
    "find_house_placements and compare_charts is UT (for example \"09:00\" is 04:00 US Central "
    "daylight time), and timestamps in their results (such as exact_utc) are UT. Convert the user's "
    "local time to UT before calling those tools.\n\n"
    "Data notices: a tool result may end with a separate block that starts with \"Data notice:\". "
    "It states a fact about the user's stored data, for example charts calculated by an older "
    "version. Tell the user about it in plain words and get their consent before running or "
    "suggesting any fix; do not apply fixes on your own. If the user asks not to be reminded, call "
    "dismiss_data_notice."
)

app = Server("w8s-astro-mcp", instructions=SERVER_INSTRUCTIONS)

# Global state
logger = logging.getLogger(__name__)

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


# Tools that have moved into the registry. The rest are still listed in list_tools() and routed
# in _dispatch_tool(), and move over group by group.
registry = ToolRegistry([
    *chart_tools.tool_specs(),
    *transit_tools.tool_specs(),
    *profile_management.tool_specs(),
    *connection_management.tool_specs(),
    *event_management.tool_specs(),
])
tool_context = ToolContext(get_db=lambda: init_db(), get_engine=lambda: init_ephemeris())


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    # Core tools
    core_tools = [
        Tool(
            name="dismiss_data_notice",
            description=(
                "Stop the 'Data notice' about stored natal charts that need recalculating, until a "
                "different chart becomes affected. Call this ONLY when the user asks not to be "
                "reminded; it does not fix anything. Use undo=true to bring the notice back."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "undo": {
                        "type": "boolean",
                        "description": "If true, bring the notice back instead of dismissing it (default false)"
                    }
                }
            }
        ),
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
                        "description": "Birth time in HH:MM format (24-hour), local time at the birth location (converted to UT using the timezone)"
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
                        "description": "IANA timezone of the birth location (e.g., 'America/Chicago'); used to convert the local birth time to UT"
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
    
    # Listed sorted by name. Once every tool is in the registry this is just registry.tools().
    return sorted(core_tools + registry.tools(), key=lambda tool: tool.name)



async def handle_dismiss_data_notice(arguments: Any) -> list[TextContent]:
    """Dismiss (or, with undo, bring back) the data notice about stale natal charts."""
    try:
        db = init_db()
        if (arguments or {}).get("undo"):
            if db.restore_notice(chart_health.NOTICE_KEY):
                text = ("The data notice is back on. It will appear again if any stored chart "
                        "still needs recalculating.")
            else:
                text = "No notice was dismissed, so there is nothing to bring back."
            return [TextContent(type="text", text=text)]

        health = chart_health.check_natal_chart_health(db, init_ephemeris())   # fresh, not the cached result
        if health.stale == 0:
            return [TextContent(type="text", text="Nothing to dismiss: no stored natal chart needs recalculating.")]
        db.dismiss_notice(chart_health.NOTICE_KEY, list(health.stale_ids))
        noun, verb = ("chart", "needs") if health.stale == 1 else ("charts", "need")
        return [TextContent(type="text", text=(
            f"Dismissed the data notice for {health.stale} stored natal {noun} that still {verb} recalculating. "
            "It will come back if a different chart is affected. Nothing was fixed: to recalculate, run "
            "`w8s-astro-recalculate --all`. To bring the notice back, call dismiss_data_notice with undo=true."
        ))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def get_profile_info(profile_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Name, id and birth time of the given profile (the owner's when None), and whether
    another profile has the same name. Returns {} if it can't be found, so callers can
    carry on without it.
    """
    try:
        db = init_db()
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


async def handle_visualize_placement_dials(arguments: dict) -> list[TextContent]:
    """Handle visualize_placement_dials tool call. Extracted for testability."""
    try:
        chart = get_natal_chart_data(tool_context, profile_id=arguments.get("profile_id"))
        info = get_profile_info(arguments.get("profile_id"))
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


# Tools whose output depends on stored natal charts. Only these can carry a data notice.
NATAL_NOTICE_TOOLS = {"visualize_placement_dials"} | registry.natal_notice_tools()
_notice_gate = DataNoticeGate()


def _json_with_notice(result: list[TextContent], notice: str) -> list[TextContent]:
    """Put the notice inside JSON output (a `notices` list) so the JSON stays parseable."""
    try:
        payload = json.loads(result[0].text)
    except (ValueError, IndexError, TypeError):
        return result
    payload.setdefault("notices", []).append(notice)
    return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False)), *result[1:]]


def _with_data_notice(name: str, arguments: Any, result: list[TextContent]) -> list[TextContent]:
    """Add a data notice when stored natal charts predate the local-time -> UT fix.

    The original output is never altered: text tools get a separate extra block (at most once per
    interval); JSON output carries the notice inside a `notices` list. The check is a courtesy and
    must never break a tool call.
    """
    if name not in NATAL_NOTICE_TOOLS:
        return result
    try:
        db = init_db()
        health = chart_health.current_health(db, init_ephemeris())
        notice = data_notice(health)
        if notice is None or chart_health.notice_dismissed(db, health):
            return result
        if (arguments or {}).get("format") == "json":
            return _json_with_notice(result, notice)
        if _notice_gate.should_show():
            return [*result, TextContent(type="text", text=notice)]
    except Exception:
        pass
    return result


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls, adding a data notice when stored charts need recalculating."""
    result = await _dispatch_tool(name, arguments)
    return _with_data_notice(name, arguments, result)


async def _dispatch_tool(name: str, arguments: Any) -> list[TextContent]:
    """Route a tool call to its handler."""

    if name == "dismiss_data_notice":
        return await handle_dismiss_data_notice(arguments)
    
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
            
            # Owner profile
            profile = db.get_owner_profile()
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
                response += "## Owner Profile\nNot configured. Run setup_owner to set.\n\n"
            
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
    
    
    elif name == "visualize_placement_dials":
        return await handle_visualize_placement_dials(arguments)

    else:
        result = await registry.call(name, arguments, tool_context)
        if result is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        return result


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def run():
    """Sync entry point for the [project.scripts] console_scripts wrapper.

    pip-generated entry points call the target function directly, so an
    async def would return a coroutine object rather than running it.
    This thin wrapper ensures asyncio.run() is always used.
    """
    asyncio.run(main())


if __name__ == "__main__":
    run()
