"""Every tool the server advertises must be routable.

`list_tools()` and `_dispatch_tool()` each carry their own list of tool names, so a tool can be
advertised and still fall through to "Unknown tool". `setup_owner` did exactly that after
`set_current_profile` was removed in v0.12.0. Tests that call `handle_*()` directly skip dispatch and
cannot see this, so this test goes through `_dispatch_tool`, the same path `call_tool` uses.
"""

import pytest

import w8s_astro_mcp.server as srv
from w8s_astro_mcp.database import initialize_database
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper


@pytest.fixture
def server_on_temp_db(tmp_path, monkeypatch):
    """The server module wired to an empty temporary database and a temporary working directory."""
    path = tmp_path / "astro.db"
    initialize_database(path, echo=False)
    monkeypatch.setattr(srv, "db_helper", DatabaseHelper(db_path=str(path)))
    monkeypatch.setattr(srv, "ephemeris", None)   # monkeypatch restores whatever init_ephemeris() sets
    monkeypatch.chdir(tmp_path)                    # tools with a default output path write here
    return srv


async def test_every_advertised_tool_is_routable(server_on_temp_db):
    advertised = [tool.name for tool in await srv.list_tools()]
    assert advertised, "list_tools() returned nothing"

    unroutable = []
    for name in advertised:
        # Empty arguments: most tools answer with an error message, which is fine. Only a reply that
        # says the tool is unknown means the name is advertised but not routed.
        result = await srv._dispatch_tool(name, {})
        if result[0].text.startswith("Unknown"):
            unroutable.append(name)

    assert unroutable == [], f"advertised but not routed: {unroutable}"
