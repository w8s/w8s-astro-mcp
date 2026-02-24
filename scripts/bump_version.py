#!/usr/bin/env python3
"""
Version bump script for w8s-astro-mcp.

Usage:
    python scripts/bump_version.py 0.11.0
    python scripts/bump_version.py 0.11.0 --dry-run

Updates:
    - pyproject.toml        (version = "...")
    - server.json           (version + packages[].version)
    - CHANGELOG.md          ([Unreleased] → [X.Y.Z] — YYYY-MM-DD)

Does NOT commit or tag — run the release workflow after reviewing the diff.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent


def current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    m = re.search(r'^version = "(.+)"', text, re.MULTILINE)
    if not m:
        sys.exit("ERROR: could not find version in pyproject.toml")
    return m.group(1)


def bump_pyproject(new: str, dry_run: bool) -> bool:
    path = ROOT / "pyproject.toml"
    old_text = path.read_text()
    new_text = re.sub(
        r'^(version = ")[^"]+(")',
        rf'\g<1>{new}\2',
        old_text,
        count=1,
        flags=re.MULTILINE,
    )
    if old_text == new_text:
        print("  SKIP  pyproject.toml — no change")
        return False
    if not dry_run:
        path.write_text(new_text)
    print(f"  {'DRY ' if dry_run else ''}BUMP  pyproject.toml  version → {new}")
    return True


def bump_server_json(new: str, dry_run: bool) -> bool:
    path = ROOT / "server.json"
    data = json.loads(path.read_text())

    changed = False
    if data.get("version") != new:
        data["version"] = new
        changed = True
    for pkg in data.get("packages", []):
        if pkg.get("version") != new:
            pkg["version"] = new
            changed = True

    if not changed:
        print("  SKIP  server.json — no change")
        return False

    if not dry_run:
        path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  {'DRY ' if dry_run else ''}BUMP  server.json     version → {new}")
    return True


def bump_changelog(new: str, dry_run: bool) -> bool:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text()
    today = date.today().strftime("%Y-%m-%d")

    # Match any [Unreleased ...] header line
    pattern = re.compile(r"^## \[Unreleased\][^\n]*", re.MULTILINE)
    if not pattern.search(text):
        print("  SKIP  CHANGELOG.md — no [Unreleased] section found")
        return False

    new_text = pattern.sub(f"## [{new}] — {today}", text, count=1)
    if not dry_run:
        path.write_text(new_text)
    print(f"  {'DRY ' if dry_run else ''}BUMP  CHANGELOG.md   [Unreleased] → [{new}] — {today}")
    return True


def validate_semver(v: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        sys.exit(f"ERROR: '{v}' is not valid semver (expected X.Y.Z)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump w8s-astro-mcp version")
    parser.add_argument("version", help="New version, e.g. 0.11.0")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    validate_semver(args.version)
    old = current_version()

    if old == args.version:
        sys.exit(f"ERROR: already at version {old}")

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Bumping {old} → {args.version}\n")

    bump_pyproject(args.version, args.dry_run)
    bump_server_json(args.version, args.dry_run)
    bump_changelog(args.version, args.dry_run)

    if not args.dry_run:
        print(f"""
Next steps:
  git add pyproject.toml server.json CHANGELOG.md
  git commit -m "release: bump version to {args.version}"
  git tag {args.version}
  git push origin main {args.version}
""")
    else:
        print("\n(dry run — no files written)")


if __name__ == "__main__":
    main()
