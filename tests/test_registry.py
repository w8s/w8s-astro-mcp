"""The tool registry: ordering, duplicate and mismatch checks, routing, and the notice flag."""

import pytest
from mcp.types import TextContent, Tool

import w8s_astro_mcp.server as srv
from w8s_astro_mcp.registry import ToolContext, ToolRegistry, ToolSpec, bind_handlers


def _tool(name: str) -> Tool:
    return Tool(name=name, description=name, inputSchema={"type": "object", "properties": {}})


async def _echo(ctx, arguments):
    return [TextContent(type="text", text=f"echo {arguments}")]


def _ctx() -> ToolContext:
    return ToolContext(get_db=lambda: "db", get_engine=lambda: "engine")


def test_tools_keep_registration_order():
    registry = ToolRegistry([ToolSpec(_tool(n), _echo) for n in ("b", "a", "c")])
    assert [t.name for t in registry.tools()] == ["b", "a", "c"]
    assert registry.names() == ["b", "a", "c"]


def test_registering_a_name_twice_is_an_error():
    with pytest.raises(ValueError, match="registered twice: a"):
        ToolRegistry([ToolSpec(_tool("a"), _echo), ToolSpec(_tool("a"), _echo)])


async def test_call_runs_the_handler_with_context_and_arguments():
    seen = {}

    async def handler(ctx, arguments):
        seen["db"], seen["engine"] = ctx.db, ctx.engine
        return [TextContent(type="text", text="ok")]

    registry = ToolRegistry([ToolSpec(_tool("a"), handler)])
    result = await registry.call("a", {"x": 1}, _ctx())
    assert result[0].text == "ok"
    assert seen == {"db": "db", "engine": "engine"}


async def test_call_returns_none_for_an_unknown_tool():
    assert await ToolRegistry().call("nope", {}, _ctx()) is None


def test_context_creates_resources_only_when_asked():
    made = []
    ctx = ToolContext(get_db=lambda: made.append("db") or "db", get_engine=lambda: made.append("engine") or "e")
    assert made == []
    assert ctx.db == "db"
    assert made == ["db"]


def test_bind_handlers_rejects_a_schema_without_a_handler():
    with pytest.raises(ValueError, match=r"no handler for \['b'\]"):
        bind_handlers([_tool("a"), _tool("b")], {"a": _echo})


def test_bind_handlers_rejects_a_handler_without_a_schema():
    with pytest.raises(ValueError, match=r"no schema for \['b'\]"):
        bind_handlers([_tool("a")], {"a": _echo, "b": _echo})


def test_bind_handlers_rejects_a_natal_flag_on_an_unknown_tool():
    with pytest.raises(ValueError, match=r"unknown tools: \['zzz'\]"):
        bind_handlers([_tool("a")], {"a": _echo}, natal_chart_tools=frozenset({"zzz"}))


def test_natal_flag_feeds_the_notice_list():
    specs = bind_handlers([_tool("a"), _tool("b")], {"a": _echo, "b": _echo}, frozenset({"b"}))
    assert ToolRegistry(specs).natal_notice_tools() == {"b"}


def test_server_notice_list_still_covers_the_connection_chart():
    assert "get_connection_chart" in srv.NATAL_NOTICE_TOOLS
    assert "get_natal_chart" in srv.NATAL_NOTICE_TOOLS
