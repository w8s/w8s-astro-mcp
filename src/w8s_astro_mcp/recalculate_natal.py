"""Recalculate stored natal charts (and, optionally, saved event charts) with correct time handling.

Before v0.13.1 the birth time (or event time) was passed to the ephemeris as if it were already UT,
even though it is a local time with a timezone. Every chart calculated that way has the wrong
Ascendant, MC, houses and Moon. This tool recalculates charts from the stored local data.

    w8s-astro-recalculate --all                 # dry run: report what would change
    w8s-astro-recalculate --all --apply         # back up the database, then recalculate
    w8s-astro-recalculate --profile-id 3 --apply
    w8s-astro-recalculate --all --events --apply   # also saved event charts

It is safe to run more than once: charts that are already correct are left alone, and nothing is
backed up or written when there is nothing to change.
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .database import get_database_path, get_session
from .models import ConnectionMember, Event, Profile
from .tools.analysis_tools import find_planets_in_houses
from .utils.db_helpers import DatabaseHelper
from .utils.ephemeris import EphemerisEngine, EphemerisError
from .utils.position_utils import sign_to_absolute_position
from .utils.timezones import TimezoneError, utc_engine_args

PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
TOLERANCE_DEGREES = 0.001
PLACEHOLDER_TIMES = {"12:00", "12:00:00"}


def _dms(degree: float) -> str:
    whole = int(degree)
    minutes = round((degree - whole) * 60)
    if minutes == 60:
        whole, minutes = whole + 1, 0
    return f"{whole}°{minutes:02d}'"


def _absolute(position: Dict[str, Any]) -> float:
    if "absolute_position" in position:
        return float(position["absolute_position"])
    return sign_to_absolute_position(position["sign"], position["degree"])


def _same_positions(stored: Dict[str, Dict[str, Any]], fresh: Dict[str, Dict[str, Any]]) -> bool:
    """True if two {name: position} maps hold the same places (within a tiny tolerance)."""
    if set(stored) != set(fresh):
        return False
    for name, position in fresh.items():
        if stored[name]["sign"] != position["sign"]:
            return False
        if abs(_absolute(stored[name]) - _absolute(position)) > TOLERANCE_DEGREES:
            return False
    return True


def _chart_matches(stored: Dict[str, Any], fresh: Dict[str, Any]) -> bool:
    return all(_same_positions(stored[part], fresh[part]) for part in ("planets", "houses", "points"))


def _profile_report(profile, ut_date: str, ut_time: str, tz: str, stored: Dict, fresh: Dict) -> List[str]:
    lines = [f"{profile.name} (id {profile.id}): born {profile.birth_date} {profile.birth_time} {tz} -> {ut_date} {ut_time} UT"]
    if stored["planets"]:
        parts = []
        for label, part, key in (("Ascendant", "points", "Ascendant"), ("MC", "points", "MC"), ("Moon", "planets", "Moon")):
            old, new = stored[part][key], fresh[part][key]
            parts.append(f"{label} {old['sign']} {_dms(old['degree'])} -> {new['sign']} {_dms(new['degree'])}")
        lines.append("    " + " | ".join(parts))
        old_houses = find_planets_in_houses(stored["planets"], stored["houses"])["placements"]
        new_houses = find_planets_in_houses(fresh["planets"], fresh["houses"])["placements"]
        moved = sum(old_houses[p] != new_houses[p] for p in PLANETS)
        sign_changes = [f"{p} {stored['planets'][p]['sign']}->{fresh['planets'][p]['sign']}"
                        for p in PLANETS if stored["planets"][p]["sign"] != fresh["planets"][p]["sign"]]
        lines.append(f"    {moved} of 10 planets change house; "
                     f"{'sign changes: ' + ', '.join(sign_changes) if sign_changes else 'no planet changes sign'}")
    else:
        lines.append("    no stored chart (it will be calculated correctly the first time it is needed)")
    if str(profile.birth_time) in PLACEHOLDER_TIMES:
        lines.append("    note: 12:00 is often a placeholder for an unknown birth time; "
                     "angles and houses are not meaningful either way")
    return lines


def _select_profile_ids(db: DatabaseHelper, args) -> List[int]:
    with get_session(db.engine) as session:
        existing = [row[0] for row in session.query(Profile.id).order_by(Profile.id).all()]
    return existing if args.all else [pid for pid in dict.fromkeys(args.profile_id) if pid in existing]


def _connections_of(db: DatabaseHelper, profile_ids: Sequence[int]) -> List[int]:
    with get_session(db.engine) as session:
        rows = session.query(ConnectionMember.connection_id).filter(
            ConnectionMember.profile_id.in_(list(profile_ids))).distinct().all()
    return sorted(row[0] for row in rows)


def _backup(db_path: Path, backup_dir: Optional[Path]) -> Path:
    directory = backup_dir or db_path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"astro-before-recalculate-{datetime.now():%Y%m%d-%H%M%S}.db"
    source, copy = sqlite3.connect(str(db_path)), sqlite3.connect(str(target))
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()
    return target


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="w8s-astro-recalculate",
        description="Recalculate stored natal charts (and optionally saved event charts) with the "
                    "birth/event time converted from local time to UT. Dry run unless --apply is given.",
    )
    parser.add_argument("--db", help="path to astro.db (default: ~/.w8s-astro-mcp/astro.db)")
    parser.add_argument("--all", action="store_true", help="recalculate every profile")
    parser.add_argument("--profile-id", type=int, action="append", default=[],
                        help="recalculate this profile (repeat for several)")
    parser.add_argument("--events", action="store_true",
                        help="also recalculate saved event charts (all of them with --all, "
                             "otherwise those attached to the selected profiles)")
    parser.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    parser.add_argument("--backup-dir", help="where to put the pre-change backup (default: <db folder>/backups)")
    args = parser.parse_args(argv)
    if not (args.all or args.profile_id):
        parser.error("choose which profiles to recalculate: --all or --profile-id ID")

    db_path = Path(args.db) if args.db else get_database_path()
    if not db_path.is_file():
        print(f"Database not found: {db_path}")
        return 1

    db = DatabaseHelper(db_path=str(db_path))
    engine = EphemerisEngine()
    errors = 0
    profile_changes: List[Any] = []     # (profile, fresh chart)
    event_changes: List[Any] = []       # (event id, fresh chart)

    print(f"Database: {db_path}\n")
    profile_ids = _select_profile_ids(db, args)
    if not profile_ids:
        print("No matching profiles.")
    for pid in profile_ids:
        profile = db.get_profile_by_id(pid)
        try:
            location = db.get_location_by_id(profile.birth_location_id)
            ut_date, ut_time = utc_engine_args(profile.birth_date, profile.birth_time, location.timezone)
            fresh = engine.get_chart(location.latitude, location.longitude, ut_date, ut_time, "P")
        except (TimezoneError, EphemerisError, AttributeError) as exc:
            errors += 1
            print(f"{profile.name} (id {profile.id}): cannot recalculate: {exc}\n")
            continue
        stored = db.get_natal_chart_data(profile)
        for line in _profile_report(profile, ut_date, ut_time, location.timezone, stored, fresh):
            print(line)
        if not stored["planets"]:
            print()
            continue
        if _chart_matches(stored, fresh):
            print("    already correct\n")
        else:
            print(f"    {'recalculated' if args.apply else 'would change'}\n")
            profile_changes.append((profile, fresh))

    if args.events:
        with get_session(db.engine) as session:
            events = [(e.id, e.label, e.event_date, e.event_time, e.latitude, e.longitude, e.timezone, e.profile_id)
                      for e in session.query(Event).order_by(Event.id).all()]
        for event_id, label, date, time, lat, lon, tz, event_profile in events:
            if not args.all and event_profile not in profile_ids:
                continue
            try:
                ut_date, ut_time = utc_engine_args(date, time, tz)
                fresh = engine.get_chart(lat, lon, ut_date, ut_time, "P")
            except (TimezoneError, EphemerisError) as exc:
                errors += 1
                print(f"event '{label}': cannot recalculate: {exc}\n")
                continue
            print(f"event '{label}': {date} {time} {tz} -> {ut_date} {ut_time} UT")
            if _chart_matches(db.get_event_chart_positions(event_id), fresh):
                print("    already correct\n")
            else:
                print(f"    {'recalculated' if args.apply else 'would change'}\n")
                event_changes.append((event_id, fresh))

    changes = len(profile_changes) + len(event_changes)
    if not changes:
        print("Nothing to change: every selected chart is already correct." if not errors
              else "Nothing could be changed (see the errors above).")
        return 1 if errors else 0

    if not args.apply:
        print(f"DRY RUN — nothing was written. Re-run with --apply to recalculate {changes} chart(s).")
        return 1 if errors else 0

    backup = _backup(db_path, Path(args.backup_dir) if args.backup_dir else None)
    print(f"Backup: {backup}")
    for profile, fresh in profile_changes:
        db.save_natal_chart(profile, fresh, profile.preferred_house_system_id or 1)
    for event_id, fresh in event_changes:
        db.replace_event_chart_positions(event_id, fresh)
    for connection_id in _connections_of(db, [profile.id for profile, _ in profile_changes]):
        db.invalidate_connection_charts(connection_id)
    print(f"Recalculated {len(profile_changes)} profile(s) and {len(event_changes)} event chart(s).")
    return 1 if errors else 0


def run() -> None:
    """Console-script entry point (must be synchronous)."""
    sys.exit(main())


if __name__ == "__main__":
    run()
