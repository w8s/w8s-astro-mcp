"""The GitHub Release notes come from the version's CHANGELOG section.

The publish workflow used an awk range whose start line also matched its end pattern, so it extracted
nothing for any version and the 0.12.1 release was published with empty notes. The extraction now lives
in scripts/release_notes.py, which is tested here, and the workflow fails loudly if a section is missing
or empty instead of publishing blank notes.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "release_notes.py"
CHANGELOG = ROOT / "CHANGELOG.md"
WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"


def _load():
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE = """# Changelog

Intro text.

## [Unreleased]

### Added

- something not released yet

## [1.2.0] — 2026-02-01

### Fixed

- the newest release

## [1.1.10] — 2026-01-15

- an older release with a look-alike number

## [1.1.1] — 2026-01-01

- the oldest release
"""


class TestExtract:
    def test_returns_the_section_without_its_heading(self):
        text = _load().extract(SAMPLE, "1.2.0")
        assert text == "### Fixed\n\n- the newest release\n"

    def test_stops_at_the_next_heading(self):
        assert "look-alike" not in _load().extract(SAMPLE, "1.2.0")

    def test_the_last_section_runs_to_the_end_of_the_file(self):
        assert _load().extract(SAMPLE, "1.1.1") == "- the oldest release\n"

    def test_a_version_is_not_a_prefix_of_another(self):
        assert _load().extract(SAMPLE, "1.1.1") != _load().extract(SAMPLE, "1.1.10")
        assert "look-alike" in _load().extract(SAMPLE, "1.1.10")

    def test_the_unreleased_section_is_never_included(self):
        assert "not released yet" not in _load().extract(SAMPLE, "1.2.0")

    def test_missing_version_raises(self):
        with pytest.raises(LookupError, match="9.9.9"):
            _load().extract(SAMPLE, "9.9.9")

    def test_empty_section_raises(self):
        with pytest.raises(LookupError, match="empty"):
            _load().extract("## [2.0.0] — 2026-03-01\n\n## [1.0.0] — 2026-01-01\n\n- x\n", "2.0.0")


class TestRealChangelog:
    """Every released version in the real CHANGELOG must produce notes, or a release would be blank."""

    VERSIONS = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG.read_text(encoding="utf-8"), re.M)

    def test_there_are_released_versions_to_check(self):
        assert self.VERSIONS

    @pytest.mark.parametrize("version", VERSIONS)
    def test_each_released_version_has_notes(self, version):
        notes = _load().extract(CHANGELOG.read_text(encoding="utf-8"), version)
        assert notes.strip()
        assert not notes.startswith("## [")


class TestCommandLine:
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_prints_the_notes(self, tmp_path):
        path = tmp_path / "CHANGELOG.md"
        path.write_text(SAMPLE, encoding="utf-8")
        result = self._run("1.2.0", "--changelog", str(path))
        assert result.returncode == 0
        assert result.stdout == "### Fixed\n\n- the newest release\n"

    def test_fails_loudly_for_a_missing_version(self, tmp_path):
        path = tmp_path / "CHANGELOG.md"
        path.write_text(SAMPLE, encoding="utf-8")
        result = self._run("9.9.9", "--changelog", str(path))
        assert result.returncode == 1
        assert "9.9.9" in result.stderr and result.stdout == ""


class TestWorkflow:
    def test_workflow_uses_the_tested_script(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "scripts/release_notes.py" in text

    def test_the_broken_awk_range_is_gone(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "awk " not in text
