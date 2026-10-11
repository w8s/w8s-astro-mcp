"""The tool registry: what the server advertises, and how each call is routed.

A tool is one `ToolSpec`: its MCP schema, its handler, and whether its output depends on stored
natal charts. `list_tools`, routing and the data-notice list all read from the registry, so a tool
cannot be advertised without a handler, and a handler cannot be added without being advertised.

Handlers take `(ctx, arguments)`. `ToolContext` supplies the database and the ephemeris engine on
demand, so a test builds its own context instead of patching module globals.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional

from mcp.types import TextContent, Tool

from .utils.db_helpers import DatabaseHelper
from .utils.ephemeris import EphemerisEngine


@dataclass
class ToolContext:
    """The shared resources a handler may use, created only when first asked for."""

    get_db: Callable[[], DatabaseHelper]
    get_engine: Callable[[], EphemerisEngine]

    @property
    def db(self) -> DatabaseHelper:
        return self.get_db()

    @property
    def engine(self) -> EphemerisEngine:
        return self.get_engine()


Handler = Callable[[ToolContext, Any], Awaitable[list[TextContent]]]


@dataclass(frozen=True)
class ToolSpec:
    """One tool: schema, handler, and whether a stale-chart data notice can apply to it."""

    tool: Tool
    handler: Handler
    uses_natal_charts: bool = False

    @property
    def name(self) -> str:
        return self.tool.name


class ToolRegistry:
    """A set of tools, listed sorted by name so the order never depends on registration order."""

    def __init__(self, specs: Iterable[ToolSpec] = ()):
        self._specs: dict[str, ToolSpec] = {}
        for spec in specs:
            self.add(spec)

    def add(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"tool registered twice: {spec.name}")
        self._specs[spec.name] = spec

    def tools(self) -> list[Tool]:
        return [self._specs[name].tool for name in self.names()]

    def names(self) -> list[str]:
        return sorted(self._specs)

    def natal_notice_tools(self) -> frozenset[str]:
        """Names of tools whose output depends on stored natal charts."""
        return frozenset(name for name, spec in self._specs.items() if spec.uses_natal_charts)

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    async def call(
        self, name: str, arguments: Any, ctx: ToolContext
    ) -> Optional[list[TextContent]]:
        """Run a tool; None when the registry has no tool of that name."""
        spec = self._specs.get(name)
        if spec is None:
            return None
        return await spec.handler(ctx, arguments)


def bind_handlers(
    tools: list[Tool],
    handlers: dict[str, Handler],
    natal_chart_tools: frozenset[str] = frozenset(),
) -> list[ToolSpec]:
    """Pair a module's tool schemas with its handlers.

    Fails loudly if the two disagree, so a module cannot ship a schema with no handler or a
    handler with no schema.
    """
    advertised = {t.name for t in tools}
    if advertised != set(handlers):
        raise ValueError(
            "tool schemas and handlers differ: "
            f"no handler for {sorted(advertised - set(handlers))}, "
            f"no schema for {sorted(set(handlers) - advertised)}"
        )
    unknown = natal_chart_tools - advertised
    if unknown:
        raise ValueError(f"natal-chart flag on unknown tools: {sorted(unknown)}")
    return [
        ToolSpec(tool=t, handler=handlers[t.name], uses_natal_charts=t.name in natal_chart_tools)
        for t in tools
    ]
