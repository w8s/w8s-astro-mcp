"""Are the stored natal charts correct? Shared by the data notice and the recalculation tool.

Versions before 0.14.0 calculated natal charts from the local birth time taken as UT. A stored chart
is "stale" when it differs from a correct calculation from the profile's local birth data. The check
needs no stored version marker, so it repeats until the charts are recalculated and then goes quiet
on its own.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from ..database import get_session
from ..models import Profile
from .ephemeris import EphemerisError
from .position_utils import sign_to_absolute_position
from .timezones import TimezoneError, utc_engine_args

TOLERANCE_DEGREES = 0.001
HEALTH_TTL_SECONDS = 600          # how long a health result is reused
NOTICE_INTERVAL_SECONDS = 1800    # at most one text notice per this interval

CHANGELOG_URL = "https://github.com/w8s/w8s-astro-mcp/blob/main/CHANGELOG.md"

# Key under which a dismissal of the natal-chart notice is stored (see DismissedNotice).
NOTICE_KEY = "natal-utc-fix"


# ---------------------------------------------------------------------------
# Comparing charts
# ---------------------------------------------------------------------------

def _absolute(position: Dict[str, Any]) -> float:
    if "absolute_position" in position:
        return float(position["absolute_position"])
    return sign_to_absolute_position(position["sign"], position["degree"])


def positions_match(stored: Dict[str, Dict[str, Any]], fresh: Dict[str, Dict[str, Any]]) -> bool:
    """True if two {name: position} maps hold the same places (within a tiny tolerance)."""
    if set(stored) != set(fresh):
        return False
    for name, position in fresh.items():
        if stored[name]["sign"] != position["sign"]:
            return False
        if abs(_absolute(stored[name]) - _absolute(position)) > TOLERANCE_DEGREES:
            return False
    return True


def charts_match(stored: Dict[str, Any], fresh: Dict[str, Any]) -> bool:
    return all(positions_match(stored[part], fresh[part]) for part in ("planets", "houses", "points"))


def fresh_natal_chart(db, engine, profile) -> Tuple[Dict[str, Any], str, str, str]:
    """Calculate a profile's natal chart correctly from its local birth data.

    Returns ``(chart, ut_date, ut_time, timezone)``. Raises TimezoneError, EphemerisError or
    AttributeError (missing birth location) when the profile cannot be calculated.
    """
    location = db.get_location_by_id(profile.birth_location_id)
    ut_date, ut_time = utc_engine_args(profile.birth_date, profile.birth_time, location.timezone)
    chart = engine.get_chart(location.latitude, location.longitude, ut_date, ut_time, "P")
    return chart, ut_date, ut_time, location.timezone


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChartHealth:
    checked: int    # profiles with a stored chart that could be checked
    stale: int      # of those, how many differ from a correct calculation
    # Which profiles are stale. Not part of equality: two results with the same counts are equal.
    stale_ids: Tuple[int, ...] = field(default=(), compare=False)


def check_natal_chart_health(db, engine) -> ChartHealth:
    """Compare every stored natal chart with a correct calculation."""
    with get_session(db.engine) as session:
        profile_ids = [row[0] for row in session.query(Profile.id).order_by(Profile.id).all()]

    checked = stale = 0
    stale_ids = []
    for profile_id in profile_ids:
        profile = db.get_profile_by_id(profile_id)
        stored = db.get_natal_chart_data(profile)
        if not stored["planets"]:
            continue                              # nothing stored; it will be calculated correctly on first use
        try:
            fresh, *_ = fresh_natal_chart(db, engine, profile)
        except (TimezoneError, EphemerisError, AttributeError):
            continue                              # cannot be checked (for example an unknown timezone)
        checked += 1
        if not charts_match(stored, fresh):
            stale += 1
            stale_ids.append(profile_id)
    return ChartHealth(checked=checked, stale=stale, stale_ids=tuple(stale_ids))


_cache: Dict[str, Tuple[float, ChartHealth]] = {}


def reset_cache() -> None:
    _cache.clear()


def current_health(
    db,
    engine,
    ttl_seconds: float = HEALTH_TTL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> ChartHealth:
    """Health of the stored charts, reused for ``ttl_seconds`` so tool calls stay fast."""
    key = str(db.engine.url)
    now = clock()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < ttl_seconds:
        return hit[1]
    health = check_natal_chart_health(db, engine)
    _cache[key] = (now, health)
    return health


# ---------------------------------------------------------------------------
# The notice
# ---------------------------------------------------------------------------

class DataNoticeGate:
    """Lets a text notice through at most once per interval."""

    def __init__(self, interval_seconds: float = NOTICE_INTERVAL_SECONDS,
                 clock: Callable[[], float] = time.monotonic):
        self._interval = interval_seconds
        self._clock = clock
        self._last: Optional[float] = None

    def should_show(self) -> bool:
        now = self._clock()
        if self._last is None or now - self._last >= self._interval:
            self._last = now
            return True
        return False


def notice_dismissed(db, health: ChartHealth) -> bool:
    """True if the user dismissed this notice and nothing new needs their attention.

    A dismissal records the stale profiles the user had seen. It holds while the stale profiles are
    a subset of those (fixing some does not bring it back); a *different* stale profile does.
    """
    seen = db.get_dismissed_notice(NOTICE_KEY)
    return seen is not None and set(health.stale_ids) <= set(seen)


def data_notice(health: ChartHealth) -> Optional[str]:
    """A short, factual notice for the assistant, or None when nothing is stale.

    It names no one (only counts) and states facts and options; applying a fix is the user's call.
    """
    if health.stale <= 0:
        return None
    noun = "chart" if health.checked == 1 else "charts"
    verb = "was" if health.stale == 1 else "were"
    return (
        f"Data notice: {health.stale} of {health.checked} stored natal {noun} {verb} calculated by "
        "a version of w8s-astro-mcp before 0.14.0, which read birth times as UT instead of local time. For "
        "those charts the Ascendant, MC, houses and Moon are off by the birth location's UTC offset; "
        "planet signs are almost always unchanged.\n"
        "Fix (the user's choice): `w8s-astro-recalculate --all` shows exactly what would change; adding "
        "`--apply` recalculates, and it backs up the database first. Add `--events` to include saved "
        f"event charts. Details: {CHANGELOG_URL}\n"
        "For the assistant: tell the user about this in plain words, and get their consent before "
        "running anything. If the user asks not to be reminded, `dismiss_data_notice` stops this "
        "notice until a different chart needs attention (it does not fix anything)."
    )
