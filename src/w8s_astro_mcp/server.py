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
from .swetest_integration import SweetestIntegration, SweetestError
from .utils.install_helper import InstallationHelper
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
config: Optional[Config] = None
swetest: Optional[SweetestIntegration] = None
install_helper = InstallationHelper()


def init_config():
    """Initialize configuration."""
    global config
    if config is None:
        config = Config()
        config.load()
    return config


def init_swetest():
    """Initialize swetest integration."""
    global swetest
    if swetest is None:
        cfg = init_config()
        
        # Check if swetest is available
        diagnosis = install_helper.diagnose()
        
        if diagnosis['status'] == 'ready':
            swetest = SweetestIntegration(cfg)
        elif diagnosis['status'] == 'needs_path':
            # Found but not in PATH - use full path
            swetest = SweetestIntegration(cfg, swetest_path=diagnosis['found_at'])
        else:
            # Not installed
            raise SweetestError(
                "swetest not found. Run check_swetest_installation tool for setup instructions."
            )
    return swetest


def get_natal_chart_data(swetest_integration):
    """
    Get natal chart from configured birth data.
    Uses cached data if available, otherwise calculates and caches.
    """
    cfg = init_config()
    birth_data = cfg.get_birth_data()
    if not birth_data:
        raise SweetestError("No birth data configured. Use setup_astro_config first.")
    
    # Check cache first
    cached_chart = cfg.get_natal_chart()
    if cached_chart:
        # Remove the 'cached_at' field before returning
        chart_data = {k: v for k, v in cached_chart.items() if k != 'cached_at'}
        return chart_data
    
    # Not cached - calculate it
    chart_data = swetest_integration.get_current_transits(
        date_str=birth_data['date'],
        time_str=birth_data['time'],
        location_name='birth'  # Use birth location, not home
    )
    
    # Cache it for future use
    cfg.set_natal_chart(chart_data)
    cfg.save()
    
    return chart_data


def get_chart_for_date(swetest_integration, date_str, time_str="12:00"):
    """Get chart for specific date."""
    return swetest_integration.get_current_transits(
        date_str=date_str,
        time_str=time_str,
        location_name='current'
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
        try:
            cfg = init_config()
            st = init_swetest()  # Need swetest to calculate natal chart
            
            location = {
                "name": arguments["birth_location_name"],
                "latitude": arguments["birth_latitude"],
                "longitude": arguments["birth_longitude"],
                "timezone": arguments["birth_timezone"]
            }
            
            cfg.set_birth_data(
                arguments["birth_date"],
                arguments["birth_time"],
                location
            )
            
            # Save birth location separately
            cfg.set_location(
                "birth",
                location["latitude"],
                location["longitude"],
                location["timezone"],
                location["name"]
            )
            
            # Also save as "home" location
            cfg.set_location(
                "home",
                location["latitude"],
                location["longitude"],
                location["timezone"],
                location["name"]
            )
            cfg.set_current_location("home")
            
            # Calculate and cache natal chart immediately
            natal_chart = get_natal_chart_data(st)
            
            cfg.save()
            
            return [TextContent(
                type="text",
                text=f"Configuration saved!\n\nBirth Data:\n"
                     f"  Date: {arguments['birth_date']}\n"
                     f"  Time: {arguments['birth_time']}\n"
                     f"  Location: {location['name']}\n"
                     f"  Coordinates: {location['latitude']}, {location['longitude']}\n"
                     f"  Timezone: {location['timezone']}\n\n"
                     f"Natal chart calculated and cached with {len(natal_chart['planets'])} planets and {len(natal_chart['houses'])} houses.\n\n"
                     f"Home location set to: {location['name']}"
            )]
        except ConfigError as e:
            return [TextContent(type="text", text=f"Configuration error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "view_config":
        try:
            cfg = init_config()
            
            response = "# Current Configuration\n\n"
            
            # Birth data
            birth_data = cfg.get_birth_data()
            if birth_data:
                response += "## Birth Data\n"
                response += f"Date: {birth_data['date']}\n"
                response += f"Time: {birth_data['time']}\n"
                response += f"Location: {birth_data['location']['name']}\n"
                response += f"Coordinates: {birth_data['location']['latitude']}, {birth_data['location']['longitude']}\n"
                response += f"Timezone: {birth_data['location']['timezone']}\n\n"
            else:
                response += "## Birth Data\nNot configured. Use setup_astro_config to set up.\n\n"
            
            # Locations
            if cfg.data.get('locations'):
                response += "## Saved Locations\n"
                current = cfg.data['locations'].get('current')
                for name, loc in cfg.data['locations'].items():
                    if name == 'current':
                        continue
                    marker = " (current)" if name == current else ""
                    response += f"- {name}{marker}: {loc.get('name', name)} ({loc['latitude']}, {loc['longitude']})\n"
                response += "\n"
            
            # House system
            response += f"## House System\n{cfg.get_house_system()} (Placidus)\n\n"
            
            response += f"Config file: {cfg.config_path}\n"
            
            return [TextContent(type="text", text=response)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "get_natal_chart":
        try:
            st = init_swetest()
            
            # Get natal chart data
            result = get_natal_chart_data(st)
            
            # Format response
            response = f"# Natal Chart for {result['metadata']['date']} at {result['metadata']['time']}\n"
            response += f"Location: {result['metadata']['latitude']}, {result['metadata']['longitude']}\n"
            response += f"House System: {result['metadata']['house_system']}\n\n"
            
            response += "## Planetary Positions\n"
            for planet_name, data in result['planets'].items():
                response += f"- **{planet_name}**: {data['degree']:.2f}° {data['sign']}\n"
            
            response += "\n## House Cusps\n"
            for house_num in sorted(result['houses'].keys()):
                data = result['houses'][house_num]
                response += f"- House {house_num}: {data['degree']:.2f}° {data['sign']}\n"
            
            if result['points']:
                response += "\n## Angles\n"
                for point, data in result['points'].items():
                    response += f"- **{point}**: {data['degree']:.2f}° {data['sign']}\n"
            
            return [TextContent(type="text", text=response)]
        except SweetestError as e:
            return [TextContent(type="text", text=f"swetest error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    elif name == "get_transits":
        try:
            st = init_swetest()
            
            date_str = arguments.get("date")
            time_str = arguments.get("time", "12:00")
            location = arguments.get("location", "current")
            
            result = st.get_current_transits(
                date_str=date_str,
                time_str=time_str,
                location_name=location
            )
            
            # Format response
            response = f"Transits for {result['metadata']['date']} at {result['metadata']['time']}\n"
            response += f"Location: {result['metadata']['latitude']}, {result['metadata']['longitude']}\n"
            response += f"House System: {result['metadata']['house_system']}\n\n"
            
            response += "Planets:\n"
            for planet, data in result['planets'].items():
                response += f"  {planet}: {data['degree']:.2f}° {data['sign']}\n"
            
            response += "\nHouses:\n"
            for house_num in sorted(result['houses'].keys()):
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
                chart1 = get_natal_chart_data(st)
            elif chart1_date == "today":
                chart1 = st.get_current_transits(
                    date_str=None,
                    time_str=chart1_time,
                    location_name='current'
                )
            else:
                chart1 = get_chart_for_date(st, chart1_date, chart1_time)
            
            # Get chart2
            chart2_date = arguments["chart2_date"]
            chart2_time = arguments.get("chart2_time", "12:00")
            
            if chart2_date == "natal":
                chart2 = get_natal_chart_data(st)
            elif chart2_date == "today":
                chart2 = st.get_current_transits(
                    date_str=None,
                    time_str=chart2_time,
                    location_name='current'
                )
            else:
                chart2 = get_chart_for_date(st, chart2_date, chart2_time)
            
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
            st = init_swetest()
            
            # Get chart
            date = arguments["date"]
            time = arguments.get("time", "12:00")
            
            if date == "natal":
                chart = get_natal_chart_data(st)
            elif date == "today":
                chart = st.get_current_transits(
                    date_str=None,
                    time_str=time,
                    location_name='current'
                )
            else:
                chart = get_chart_for_date(st, date, time)
            
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
            st = init_swetest()
            
            # Get natal chart data
            natal_chart = get_natal_chart_data(st)
            
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
            
        except SweetestError as e:
            return [TextContent(type="text", text=f"swetest error: {e}")]
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
