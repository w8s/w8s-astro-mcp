"""scripts/bump_version.py keeps every place that records the project's version in step.

Two wart fixes, both hit while releasing 0.12.1 and 0.14.0:
  * uv.lock records the project's own version. The script did not touch it, so `uv lock --check`
    failed after every bump until the line was patched by hand.
  * server.json was rewritten with the em dash in its description escaped (\\u2014); it is kept literal.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "bump_version.py"


def _load():
    spec = importlib.util.spec_from_file_location("bump_version", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PYPROJECT = '''[project]
name = "demo-project"
version = "1.0.0"
requires-python = ">=3.10"
'''

SERVER_JSON = """{
  "name": "io.github.example/demo-project",
  "description": "Demo \u2014 with an em dash",
  "version": "1.0.0",
  "packages": [
    {
      "registryType": "pypi",
      "identifier": "demo-project",
      "version": "1.0.0"
    }
  ]
}
"""

CHANGELOG = """# Changelog

## [Unreleased]

### Added

- something

## [1.0.0] — 2026-01-01

- first release
"""

UV_LOCK = '''version = 1
requires-python = ">=3.10"

[[package]]
name = "anyio"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "demo-project"
version = "1.0.0"
source = { editable = "." }
dependencies = [
    { name = "anyio" },
]

[[package]]
name = "zeta"
version = "1.0.0"
source = { registry = "https://pypi.org/simple" }
'''


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "server.json").write_text(SERVER_JSON, encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    (tmp_path / "uv.lock").write_text(UV_LOCK, encoding="utf-8")
    bump = _load()
    monkeypatch.setattr(bump, "ROOT", tmp_path)
    return bump, tmp_path


class TestUvLock:
    def test_updates_the_projects_own_version(self, project):
        bump, root = project
        assert bump.bump_uv_lock("1.1.0", dry_run=False) is True
        text = (root / "uv.lock").read_text(encoding="utf-8")
        assert 'name = "demo-project"\nversion = "1.1.0"' in text

    def test_leaves_every_other_package_alone(self, project):
        bump, root = project
        bump.bump_uv_lock("1.1.0", dry_run=False)
        text = (root / "uv.lock").read_text(encoding="utf-8")
        assert 'name = "anyio"\nversion = "1.0.0"' in text
        assert 'name = "zeta"\nversion = "1.0.0"' in text
        before = UV_LOCK.splitlines()
        after = text.splitlines()
        assert [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [10]      # exactly one line changed

    def test_dry_run_writes_nothing(self, project):
        bump, root = project
        assert bump.bump_uv_lock("1.1.0", dry_run=True) is True
        assert (root / "uv.lock").read_text(encoding="utf-8") == UV_LOCK

    def test_no_change_when_already_at_the_version(self, project):
        bump, _ = project
        assert bump.bump_uv_lock("1.0.0", dry_run=False) is False

    def test_a_project_without_a_lock_file_is_skipped(self, project):
        bump, root = project
        (root / "uv.lock").unlink()
        assert bump.bump_uv_lock("1.1.0", dry_run=False) is False

    def test_a_lock_without_the_project_is_an_error(self, project):
        bump, root = project
        (root / "uv.lock").write_text(UV_LOCK.replace('name = "demo-project"', 'name = "someone-else"'), encoding="utf-8")
        with pytest.raises(SystemExit, match="demo-project"):
            bump.bump_uv_lock("1.1.0", dry_run=False)


class TestServerJson:
    def test_bumps_both_version_fields(self, project):
        bump, root = project
        assert bump.bump_server_json("1.1.0", dry_run=False) is True
        data = json.loads((root / "server.json").read_text(encoding="utf-8"))
        assert data["version"] == "1.1.0" and data["packages"][0]["version"] == "1.1.0"

    def test_keeps_the_em_dash_literal(self, project):
        bump, root = project
        bump.bump_server_json("1.1.0", dry_run=False)
        text = (root / "server.json").read_text(encoding="utf-8")
        assert "\u2014" in text and "\\u2014" not in text

    def test_only_the_versions_change(self, project):
        bump, root = project
        bump.bump_server_json("1.1.0", dry_run=False)
        changed = [
            (a, b) for a, b in zip(SERVER_JSON.splitlines(), (root / "server.json").read_text(encoding="utf-8").splitlines())
            if a != b
        ]
        assert len(changed) == 2 and all('"version"' in a for a, _ in changed)


class TestWholeScript:
    def _run(self, bump, monkeypatch, *args):
        monkeypatch.setattr(sys, "argv", ["bump_version.py", *args])
        bump.main()

    def test_bumps_all_four_files(self, project, monkeypatch):
        bump, root = project
        self._run(bump, monkeypatch, "1.1.0")
        assert 'version = "1.1.0"' in (root / "pyproject.toml").read_text(encoding="utf-8")
        assert json.loads((root / "server.json").read_text(encoding="utf-8"))["version"] == "1.1.0"
        assert re.search(r"^## \[1\.1\.0\] — \d{4}-\d{2}-\d{2}$", (root / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        assert 'name = "demo-project"\nversion = "1.1.0"' in (root / "uv.lock").read_text(encoding="utf-8")

    def test_dry_run_writes_nothing(self, project, monkeypatch):
        bump, root = project
        self._run(bump, monkeypatch, "1.1.0", "--dry-run")
        assert (root / "pyproject.toml").read_text(encoding="utf-8") == PYPROJECT
        assert (root / "server.json").read_text(encoding="utf-8") == SERVER_JSON
        assert (root / "CHANGELOG.md").read_text(encoding="utf-8") == CHANGELOG
        assert (root / "uv.lock").read_text(encoding="utf-8") == UV_LOCK


class TestRealRepository:
    """The real files must agree, or `uv lock --check` fails and a release ships with mismatched versions."""

    def test_pyproject_server_json_and_uv_lock_record_the_same_version(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        version = re.search(r'^version = "(.+)"', pyproject, re.M).group(1)
        name = re.search(r'^name = "(.+)"', pyproject, re.M).group(1)

        server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
        assert server["version"] == version
        assert all(package["version"] == version for package in server["packages"])

        lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
        assert f'[[package]]\nname = "{name}"\nversion = "{version}"' in lock
