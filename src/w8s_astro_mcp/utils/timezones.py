"""Convert local wall-clock times to UT.

Swiss Ephemeris takes Universal Time. Several tools collect a *local* time together with an IANA
timezone (birth time, event time, electional windows); this module turns those into the UT values
the ephemeris needs, using ``zoneinfo`` so historical daylight-saving rules apply (for example, US
DST was in effect on 1981-05-06).

Edge cases:
  * An ambiguous local time (DST fall-back, the hour that happens twice) takes the first occurrence.
  * A nonexistent local time (DST spring-forward gap) is read with the pre-transition offset, which
    shifts it forward by the length of the gap.
  * Seconds are accepted and ignored: the ephemeris works to the minute.
"""

from datetime import datetime, timezone
from typing import Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimezoneError(ValueError):
    """Raised when a local time cannot be converted (bad date, time or timezone)."""


def _zone(tz_name: str) -> ZoneInfo:
    if not tz_name or not str(tz_name).strip():
        raise TimezoneError("A timezone is required (an IANA name such as 'America/Chicago').")
    name = str(tz_name).strip()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise TimezoneError(
            f"Unknown timezone {name!r}. Use an IANA name such as 'America/Chicago'."
        ) from exc


def _parse_time(time_str: str) -> Tuple[int, int]:
    parts = str(time_str).strip().split(":")
    try:
        if len(parts) not in (2, 3):
            raise ValueError("expected HH:MM")
        hour, minute = int(parts[0]), int(parts[1])
        if len(parts) == 3:
            int(parts[2])  # validate seconds, then ignore them
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("out of range")
    except ValueError as exc:
        raise TimezoneError(f"Invalid time {time_str!r}; expected HH:MM (24-hour).") from exc
    return hour, minute


def _local(date_str: str, time_str: str, tz_name: str) -> datetime:
    """A local date and time in ``tz_name`` as a timezone-aware datetime."""
    zone = _zone(tz_name)
    try:
        day = datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise TimezoneError(f"Invalid date {date_str!r}; expected YYYY-MM-DD.") from exc
    hour, minute = _parse_time(time_str)
    return day.replace(hour=hour, minute=minute, tzinfo=zone)  # fold=0: first occurrence


def local_to_utc(date_str: str, time_str: str, tz_name: str) -> datetime:
    """Convert a local date and time in ``tz_name`` to a timezone-aware UTC datetime."""
    return _local(date_str, time_str, tz_name).astimezone(timezone.utc)


def utc_offset_label(date_str: str, time_str: str, tz_name: str) -> str:
    """The UTC offset in force at a local date and time, for display: ``UTC-5``, ``UTC+5:30``, ``UTC+0``."""
    minutes = int(_local(date_str, time_str, tz_name).utcoffset().total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, rest = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours}" + (f":{rest:02d}" if rest else "")


def utc_engine_args(date_str: str, time_str: str, tz_name: str) -> Tuple[str, str]:
    """Return ``(date, time)`` strings in UT for ``EphemerisEngine.get_chart``."""
    moment = local_to_utc(date_str, time_str, tz_name)
    return moment.strftime("%Y-%m-%d"), moment.strftime("%H:%M")


def utc_to_local(moment: datetime, tz_name: str) -> datetime:
    """Convert a timezone-aware UTC datetime to local time in ``tz_name``."""
    if moment.tzinfo is None:
        raise TimezoneError("utc_to_local needs a timezone-aware datetime.")
    return moment.astimezone(_zone(tz_name))
