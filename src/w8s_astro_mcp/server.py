"""MCP server for w8s-astro-mcp."""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from .config import Config, ConfigError
from .utils.swetest_integration import SweetestIntegration, SweetestError
from .utils.install_helper import InstallationHelper
from .utils.db_helpers import DatabaseHelper
from .tools.analysis_tools import (
    compare_charts,
    find_planets_in_houses,
    format_aspect_report,
    format_house_report,
    AnalysisError
)
from .tools.visualization import create_natal_chart


# Initialize MCP server
app = Server("w8s-astro-mcp")

# Global state
db_helper: Optional[DatabaseHelper] = None
swetest: Optional[SweetestIntegration] = None
install_helper = InstallationHelper()


def init_db():
    """Initialize database helper."""
    global db_helper
    if db_helper is None:
        db_helper = DatabaseHelper()
    return db_helper


def init_swetest():
    """Initialize swetest integration."""
    global swetest
    if swetest is None:
        # Check if swetest is available
        diagnosis = install_helper.diagnose()
        
        if diagnosis['status'] == 'ready':
            swetest = SweetestIntegration()
        elif diagnosis['status'] == 'needs_path':
            # Found but not in PATH - use full path
            swetest = SweetestIntegration(swetest_path=diagnosis['found_at'])
        else:
            # Not installed
            raise SweetestError(
                "swetest not found. Run check_swetest_installation tool for setup instructions."
            )
    return swetest


def get_natal_chart_data():
    """Get natal chart from primary profile."""
    db = init_db()
    
    profile = db.get_primary_profile()
    if not profile:
        raise SweetestError("No primary profile found. Run migration script first.")
    
    return db.get_natal_chart_data(profile)


def get_chart_for_date(date_str, time_str="12:00", location=None):
    """Get chart for specific date at a location."""
    st = init_swetest()
    db = init_db()
    
    # Get location
    if location is None:
        profile = db.get_primary_profile()
        location = db.get_current_home_location(profile)
        if not location:
            raise SweetestError("No current home location found")
    
    return st.get_transits(
        latitude=location.latitude,
        longitude=location.longitude,
        date_str=date_str,
        time_str=time_str,
        house_system_code='P'  # TODO: Get from profile
    )


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="check_swetest_installation",
            description="Check if swetest (Swiss Ephemeris) is installed and get setup instructions",
            inputSchema={
                "type": "object",
                "properties": {},
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
            description="Get current planetary transits for a specific date and location",
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
                        "description": "Location name (optional, defaults to 'current')"
                    }
                }
            }
        ),
        Tool(
            name="compare_charts",
            description=(
                "Calculate aspects between two charts. "
                "Use for synastry (comparing two natal charts) or "
                "transits (comparing natal chart with current positions). "
                "Finds conjunctions, oppositions, trines, squares, sextiles, and minor aspects."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chart1_date": {
                        "type": "string",
                        "description": "Date for first chart (YYYY-MM-DD), use 'natal' for configured birth chart"
                    },
                    "chart1_time": {
                        "type": "string",
                        "description": "Time for first chart in HH:MM format (optional, defaults to 12:00)"
                    },
                    "chart2_date": {
                        "type": "string",
                        "description": "Date for second chart (YYYY-MM-DD), use 'natal' for birth chart or 'today' for current"
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



@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "check_swetest_installation":
        diagnosis = install_helper.diagnose()
        
        message = f"Status: {diagnosis['status']}\n"
        message += f"swetest in PATH: {'Yes' if diagnosis['swetest_in_path'] else 'No'}\n"
        message += f"swetest found: {'Yes' if diagnosis['swetest_found'] else 'No'}\n"
        
        if diagnosis['found_at']:
            message += f"Location: {diagnosis['found_at']}\n"
        
        message += "\nRecommendations:\n"
        for rec in diagnosis['recommendations']:
            message += f"  {rec}\n"
        
        if diagnosis['status'] == 'needs_path':
            message += "\n" + install_helper.get_quick_fix_guide(diagnosis['found_at'])
        elif diagnosis['status'] == 'not_installed':
            message += "\n" + install_helper.get_installation_guide()
        
        return [TextContent(type="text", text=message)]
    
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
            profile = db.get_primary_profile()
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
    
    elif name == "get_transits":
        try:
            st = init_swetest()
            db = init_db()
            
            date_str = arguments.get("date")
            time_str = arguments.get("time", "12:00")
            location_arg = arguments.get("location", "current")
            
            # Get profile
            profile = db.get_primary_profile()
            if not profile:
                return [TextContent(type="text", text="No primary profile found")]
            
            # Get location
            if location_arg == "current" or location_arg == "home":
                location = db.get_current_home_location(profile)
                if not location:
                    return [TextContent(type="text", text="No current home location set")]
            elif location_arg == "birth":
                location = db.get_birth_location(profile)
            else:
                # Try to find by label
                location = db.get_location_by_label(location_arg, profile)
                if not location:
                    return [TextContent(type="text", text=f"Location '{location_arg}' not found")]
            
            # Get transits from swetest
            result = st.get_transits(
                latitude=location.latitude,
                longitude=location.longitude,
                date_str=date_str,
                time_str=time_str,
                house_system_code='P'  # TODO: Get from profile
            )
            
            # 🆕 AUTO-LOG: Save this transit lookup to database
            try:
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
            response += f"Location: {location.label} ({result['metadata']['latitude']}, {result['metadata']['longitude']})\n"
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
            
        except SweetestError as e:
            return [TextContent(type="text", text=f"swetest error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "compare_charts":
        try:
            st = init_swetest()
            
            # Get chart1
            chart1_date = arguments["chart1_date"]
            chart1_time = arguments.get("chart1_time", "12:00")
            
            if chart1_date == "natal":
                chart1 = get_natal_chart_data()
            elif chart1_date == "today":
                chart1 = get_chart_for_date(None, chart1_time)
            else:
                chart1 = get_chart_for_date(chart1_date, chart1_time)
            
            # Get chart2
            chart2_date = arguments["chart2_date"]
            chart2_time = arguments.get("chart2_time", "12:00")
            
            if chart2_date == "natal":
                chart2 = get_natal_chart_data()
            elif chart2_date == "today":
                chart2 = get_chart_for_date(None, chart2_time)
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
        except SweetestError as e:
            return [TextContent(type="text", text=f"swetest error: {e}")]
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
        except SweetestError as e:
            return [TextContent(type="text", text=f"swetest error: {e}")]
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
