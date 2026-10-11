"""Shared fixtures."""

import pytest

import w8s_astro_mcp.server as srv
from tool_harness import masked
from w8s_astro_mcp.database import initialize_database
from w8s_astro_mcp.utils.db_helpers import DatabaseHelper


@pytest.fixture
def tool(tmp_path, monkeypatch):
    """Call a tool through `call_tool`; returns its masked text (all content blocks joined).

    The server runs on an empty temporary database, a temporary home directory and the built-in
    Moshier ephemeris, so results do not depend on the machine. `tool.db` is the database helper,
    `tool.home` the temporary home and `tool.tmp` the temporary working directory.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))              # Path.home() -> temporary home
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)  # force the built-in Moshier ephemeris
    monkeypatch.chdir(tmp_path)

    db_path = tmp_path / "astro.db"
    initialize_database(db_path, echo=False)
    monkeypatch.setattr(srv, "db_helper", DatabaseHelper(db_path=str(db_path)))
    monkeypatch.setattr(srv, "ephemeris", None)

    async def call(name: str, arguments: dict | None = None) -> str:
        blocks = await srv.call_tool(name, arguments or {})
        return masked("\n---\n".join(b.text for b in blocks), tmp_path)

    call.home = home
    call.db = srv.db_helper
    call.tmp = tmp_path
    return call
