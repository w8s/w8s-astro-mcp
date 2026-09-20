"""Dependabot must not propose updates that break installs.

Two are known to (see the 0.12.1 and 0.11.2 changelog entries):
  * mcp 2.x removed the Server.list_tools()/call_tool() decorators this server is built on. An
    unbounded requirement made every fresh install fail at import once 2.x was published.
  * timezonefinder 8.x pulls in a compiled dependency, so installs fail without a C toolchain (CMake).

These checks keep the ignore rules from being dropped by accident. (PyYAML is not a dependency of
this project, so the file is checked as text.)
"""

import re
from pathlib import Path

CONFIG = (Path(__file__).parent.parent / ".github" / "dependabot.yml").read_text(encoding="utf-8")


def _ignore_entry(package: str) -> str:
    """The text of the ignore entry for ``package`` (from its dependency-name line to the next entry)."""
    match = re.search(
        r'- dependency-name: "%s"\n(?P<body>(?:[ \t]+(?!- ).*\n)*)' % re.escape(package), CONFIG
    )
    assert match, f"dependabot.yml has no ignore entry for {package}"
    return match.group("body")


def test_mcp_major_updates_are_ignored():
    assert 'version-update:semver-major' in _ignore_entry("mcp")


def test_timezonefinder_8_and_later_is_ignored():
    entry = _ignore_entry("timezonefinder")
    assert '">=8.0.0"' in entry


def test_the_ignore_rules_are_under_the_python_ecosystem():
    ignore_at = CONFIG.index("ignore:")
    pip_at = CONFIG.index('package-ecosystem: "pip"')
    actions_at = CONFIG.index('package-ecosystem: "github-actions"')
    assert pip_at < ignore_at < actions_at


def test_each_ignore_rule_says_why():
    # A rule with no reason gets deleted the next time someone tidies the file.
    assert "list_tools" in CONFIG or "mcp 2" in CONFIG.lower()
    assert "CMake" in CONFIG
