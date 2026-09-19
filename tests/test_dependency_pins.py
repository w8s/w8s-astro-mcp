"""Dependency guards.

`mcp` 2.x removed the `Server.list_tools()` / `call_tool()` decorators this server is built on. With
an unbounded `mcp>=1.0.0`, every fresh install failed at import (`AttributeError: 'Server' object has
no attribute 'list_tools'`) as soon as 2.x was published. Keep the upper bound until the server is
migrated to the 2.x API.
"""

import re
from pathlib import Path

PYPROJECT = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")


def _mcp_requirement() -> str:
    # A requirement like "mcp>=1.28.1,<2" (not the "mcp" keyword or the registry name).
    match = re.search(r'"(mcp[<>=!~][^"]*)"', PYPROJECT)
    assert match, "pyproject.toml no longer declares a versioned mcp dependency"
    return match.group(1).replace(" ", "")


def test_mcp_is_bounded_below_2():
    assert "<2" in _mcp_requirement(), f"mcp must stay below 2.x, found {_mcp_requirement()!r}"


def test_mcp_lower_bound_excludes_releases_with_known_advisories():
    # mcp < 1.27.2 has advisories for the HTTP transports and experimental task handlers, and
    # < 1.28.1 for the WebSocket transport. This server is stdio-only, but there is no reason to
    # let a fresh install resolve to a version that is flagged.
    match = re.search(r"mcp>=(\d+)\.(\d+)\.(\d+)", _mcp_requirement())
    assert match, f"expected a lower bound like mcp>=1.28.1, found {_mcp_requirement()!r}"
    assert tuple(int(part) for part in match.groups()) >= (1, 28, 1)


def test_installed_mcp_still_has_the_decorators_the_server_uses():
    from mcp.server import Server

    server = Server("dependency-guard")
    assert callable(getattr(server, "list_tools", None))
    assert callable(getattr(server, "call_tool", None))
