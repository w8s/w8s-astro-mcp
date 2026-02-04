"""MCP server for w8s-astro-mcp."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from .config import Config, ConfigError
from .swetest_integration import SweetestIntegration, SweetestError
from .utils.install_helper import InstallationHelper


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
            description="Configure birth data and locations for transit calculations",
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
            
            # Also save as "home" location
            cfg.set_location(
                "home",
                location["latitude"],
                location["longitude"],
                location["timezone"],
                location["name"]
            )
            cfg.set_current_location("home")
            
            cfg.save()
            
            return [TextContent(
                type="text",
                text=f"Configuration saved!\n\nBirth Data:\n"
                     f"  Date: {arguments['birth_date']}\n"
                     f"  Time: {arguments['birth_time']}\n"
                     f"  Location: {location['name']}\n"
                     f"  Coordinates: {location['latitude']}, {location['longitude']}\n"
                     f"  Timezone: {location['timezone']}\n\n"
                     f"Home location set to: {location['name']}"
            )]
        except ConfigError as e:
            return [TextContent(type="text", text=f"Configuration error: {e}")]
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
