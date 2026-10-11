"""MCP server for w8s-astro-mcp."""

import asyncio
import json
import logging
import os
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from .registry import ToolContext, ToolRegistry
from .tools import (
    chart_tools,
    connection_management,
    event_management,
    profile_management,
    system_tools,
    transit_tools,
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

logger = logging.getLogger(__name__)


def _new_engine() -> EphemerisEngine:
    """Build the ephemeris engine, honouring an optional SE_EPHE_PATH override for the .se1 files."""
    return EphemerisEngine(ephe_path=os.environ.get("SE_EPHE_PATH") or None)


registry = ToolRegistry([
    *chart_tools.tool_specs(),
    *transit_tools.tool_specs(),
    *profile_management.tool_specs(),
    *connection_management.tool_specs(),
    *event_management.tool_specs(),
    *system_tools.tool_specs(),
])
tool_context = ToolContext(get_db=DatabaseHelper, get_engine=_new_engine)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools (sorted by name)."""
    return registry.tools()


# Tools whose output depends on stored natal charts. Only these can carry a data notice.
NATAL_NOTICE_TOOLS = registry.natal_notice_tools()
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
        db = tool_context.db
        health = chart_health.current_health(db, tool_context.engine)
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
