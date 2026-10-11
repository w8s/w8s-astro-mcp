"""System tools: ephemeris status and download, configuration view, and the data-notice switch."""

import urllib.request
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool

from ..registry import ToolContext, ToolSpec, bind_handlers
from ..utils import chart_health
from ..utils.ephemeris import EphemerisEngine


def get_system_tools() -> list[Tool]:
    return [
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
    ]


async def handle_dismiss_data_notice(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    """Dismiss (or, with undo, bring back) the data notice about stale natal charts."""
    try:
        db = ctx.db
        if (arguments or {}).get("undo"):
            if db.restore_notice(chart_health.NOTICE_KEY):
                text = ("The data notice is back on. It will appear again if any stored chart "
                        "still needs recalculating.")
            else:
                text = "No notice was dismissed, so there is nothing to bring back."
            return [TextContent(type="text", text=text)]

        health = chart_health.check_natal_chart_health(db, ctx.engine)   # fresh, not the cached result
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


async def handle_check_ephemeris(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    """Report the ephemeris mode and precision."""
    import swisseph as swe
    engine = ctx.engine
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
        lines.append("Precision: ~0.001 arcsecond (Swiss Ephemeris files)")
        lines.append(f"Ephemeris path: {engine.ephe_path}")
        if files:
            lines.append(f"Data files: {', '.join(f.name for f in sorted(files))}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_download_ephemeris_files(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    """Download the Swiss Ephemeris data files (after confirmation) and switch to them."""
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
            f"Current mode: {ctx.engine.get_mode()}",
            "After upgrade: Swiss Ephemeris (~0.001 arcsecond precision)",
            "",
            "Files to download:",
        ]
        for fname, desc, size in file_manifest:
            lines.append(f"  {fname:<16} {desc:<40} {size}")
        lines += [
            "  Total                                                    ~2.0 MB",
            "",
            "Source:      github.com/aloistr/swisseph (official Swiss Ephemeris repository)",
            f"Destination: {ephe_dir}",
            "",
            "Call again with confirm=true to proceed.",
        ]
        return [TextContent(type="text", text="\n".join(lines))]

    # Check which files are already present.
    ephe_dir.mkdir(parents=True, exist_ok=True)
    lines = ["Downloading Swiss Ephemeris data files...", ""]
    for fname, _desc, _size in file_manifest:
        dest = ephe_dir / fname
        if dest.exists():
            lines.append(f"  ✓ {fname}  already present — skipped")
        else:
            url = f"{base_url}/{fname}"
            try:
                urllib.request.urlretrieve(url, dest)
                size_kb = dest.stat().st_size // 1024
                lines.append(f"  ✓ {fname}  {size_kb} KB   saved to {ephe_dir}")
            except Exception as exc:
                lines.append(f"  ✗ {fname}  FAILED: {exc}")

    # Activate the downloaded files immediately (no restart needed).
    ctx.set_engine(EphemerisEngine(ephe_path=str(ephe_dir)))

    lines += ["", "High-precision mode active. No restart required."]
    return [TextContent(type="text", text="\n".join(lines))]


async def handle_setup_astro_config(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    """Deprecated; kept so older instructions get a pointer to the new tools."""
    return [TextContent(
        type="text",
        text="⚠️ This tool is deprecated.\n\n"
             "The w8s-astro-mcp now uses SQLite database instead of config.json.\n\n"
             "Your data has been migrated to: ~/.w8s-astro-mcp/astro.db\n\n"
             "To add new profiles or locations, use the database migration script or "
             "contact the developer for profile management tools."
    )]


async def handle_view_config(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    """Show the owner profile, saved locations and database path."""
    try:
        db = ctx.db
        
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


def tool_specs() -> list[ToolSpec]:
    """The system tools. None of them read stored natal charts, so none carries a data notice."""
    return bind_handlers(
        get_system_tools(),
        {
            "dismiss_data_notice": handle_dismiss_data_notice,
            "check_ephemeris": handle_check_ephemeris,
            "download_ephemeris_files": handle_download_ephemeris_files,
            "setup_astro_config": handle_setup_astro_config,
            "view_config": handle_view_config,
        },
    )
