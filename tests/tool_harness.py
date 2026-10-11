"""Shared helpers for tests that call tools through `call_tool` (see conftest.py for the fixture)."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import os
import re
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden"


def masked(text: str, tmp_path: Path) -> str:
    """Replace values that differ between machines and runs."""
    text = text.replace(str(tmp_path), "<TMP>")
    return re.sub(r"pysweph version: \S+", "pysweph version: <VERSION>", text)


def assert_golden(name: str, text: str) -> None:
    """Compare text with tests/golden/<name>.txt; UPDATE_GOLDEN=1 rewrites the file instead."""
    path = GOLDEN_DIR / f"{name}.txt"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        return
    assert path.exists(), f"missing golden file {path}; run with UPDATE_GOLDEN=1"
    assert text + "\n" == path.read_text(encoding="utf-8"), f"output changed for {name}"


def add_owner(tool, name="Test Owner", date="1981-05-06", time="00:50"):
    """Create a profile born in Richardson, TX and make it the owner."""
    profile = tool.db.create_profile_with_location(
        name=name,
        birth_date=date,
        birth_time=time,
        birth_location_name="Richardson, TX",
        birth_latitude=32.9483,
        birth_longitude=-96.7299,
        birth_timezone="America/Chicago",
    )
    tool.db.set_owner_profile(profile.id)
    return profile


def add_second(tool, name="Second Person", date="1990-01-15", time="12:00"):
    """Create a profile born in Seattle, WA (not the owner)."""
    return tool.db.create_profile_with_location(
        name=name,
        birth_date=date,
        birth_time=time,
        birth_location_name="Seattle, WA",
        birth_latitude=47.6062,
        birth_longitude=-122.3321,
        birth_timezone="America/Los_Angeles",
    )


@contextmanager
def context_db(db=None):
    """Run with `db` (a mock when omitted) as the server's database, then go back to the default."""
    import w8s_astro_mcp.server as srv
    srv.tool_context.set_db(db if db is not None else MagicMock())
    try:
        yield
    finally:
        srv.tool_context.set_db(None)
