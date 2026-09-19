#!/usr/bin/env python3
"""
Print the CHANGELOG section for one version, for use as GitHub Release notes.

Usage:
    python scripts/release_notes.py 0.12.1
    python scripts/release_notes.py 0.12.1 --changelog path/to/CHANGELOG.md

Prints everything under the "## [X.Y.Z] ..." heading up to the next "## [" heading (without the
heading itself). Exits with status 1 and a message on stderr if the version has no section or the
section is empty, so the release workflow fails loudly instead of publishing blank notes.

The publish workflow calls this. Preview a release's notes before tagging with the command above.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def extract(changelog: str, version: str) -> str:
    """Return the CHANGELOG section for ``version`` (without its heading), ending in a newline.

    Raises LookupError if there is no such section or it is empty.
    """
    lines = changelog.splitlines()
    heading = re.compile(r"^## \[" + re.escape(version) + r"\]")
    start = next((index for index, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise LookupError(f"No CHANGELOG section found for version {version}")

    body = []
    for line in lines[start + 1:]:
        if line.startswith("## ["):
            break
        body.append(line)

    text = "\n".join(body).strip("\n")
    if not text.strip():
        raise LookupError(f"The CHANGELOG section for version {version} is empty")
    return text + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Print the CHANGELOG section for a version.")
    parser.add_argument("version", help="version number, for example 0.12.1")
    parser.add_argument("--changelog", default=str(ROOT / "CHANGELOG.md"), help="path to CHANGELOG.md")
    args = parser.parse_args(argv)

    try:
        notes = extract(Path(args.changelog).read_text(encoding="utf-8"), args.version)
    except (LookupError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
