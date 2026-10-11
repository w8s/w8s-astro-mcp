"""Transit tools: today's sky, the log of past lookups, and ingress/station scans."""

from datetime import datetime
from typing import Any

from mcp.types import TextContent, Tool

from ..registry import ToolContext, ToolSpec, bind_handlers
from ..utils.ephemeris import EphemerisError
from ..utils.geocoding import geocode_location


# ============================================================================
# Tool Definitions
# ============================================================================

def get_transit_tools() -> list[Tool]:
    return [
        Tool(
            name="get_transits",
            description=(
                "Get planetary transits for a specific date and location. "
                "Location can be a saved label ('home', 'work', 'birth'), "
                "or any city/place name ('Seattle', 'Bangkok, Thailand', 'Paris') — "
                "unknown names are geocoded automatically. "
                "Defaults to current home location if omitted."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (optional, defaults to today)"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM format, interpreted as UT (optional, defaults to 12:00)"
                    },
                    "location": {
                        "type": "string",
                        "description": (
                            "Saved label ('home', 'work', 'birth') or any city name "
                            "('Bangkok, Thailand', 'Seattle, WA'). Defaults to 'current'."
                        )
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to query (from list_profiles). Defaults to owner profile."
                    }
                }
            }
        ),
        Tool(
            name="get_transit_history",
            description=(
                "Query historical transit lookups stored in the database for a profile. Defaults to the owner profile. "
                "Supports filtering by date range, planet, and sign. "
                "Examples: 'show me last month\\'s transits', "
                "'when was Mercury in Capricorn?', 'what sign was Jupiter in last year?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "after": {
                        "type": "string",
                        "description": "Return lookups on or after this date (YYYY-MM-DD, optional)"
                    },
                    "before": {
                        "type": "string",
                        "description": "Return lookups on or before this date (YYYY-MM-DD, optional)"
                    },
                    "planet": {
                        "type": "string",
                        "description": "Filter by planet name, e.g. 'Mercury' (optional)"
                    },
                    "sign": {
                        "type": "string",
                        "description": "Filter by zodiac sign, e.g. 'Capricorn' — requires planet (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of results to return (default 20, max 100)"
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to query (from list_profiles). Defaults to owner profile."
                    }
                }
            }
        ),
        Tool(
            name="find_last_transit",
            description=(
                "Find the most recent logged transit where a planet met specific conditions. "
                "Examples: 'when was Mercury last retrograde?', "
                "'when was the Moon last in Scorpio?', "
                "'when was Mars last in my 7th house?'. "
                "Requires at least one of: sign, retrograde, or house."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "planet": {
                        "type": "string",
                        "description": "Planet name, e.g. 'Mercury', 'Mars'"
                    },
                    "sign": {
                        "type": "string",
                        "description": "Zodiac sign to match, e.g. 'Capricorn' (optional)"
                    },
                    "retrograde": {
                        "type": "boolean",
                        "description": "If true, find last retrograde; if false, find last direct (optional)"
                    },
                    "house": {
                        "type": "integer",
                        "description": "Natal house number to match, 1-12 (optional)"
                    },
                    "profile_id": {
                        "type": "integer",
                        "description": "Profile ID to query (from list_profiles). Defaults to owner profile."
                    }
                },
                "required": ["planet"]
            }
        ),
        Tool(
            name="get_ingresses",
            description=(
                "Scan the ephemeris for upcoming or recent planetary sign ingresses "
                "and stations (retrograde/direct). "
                "Examples: 'what transits are coming up this month?', "
                "'when does Mercury go retrograde?', "
                "'show me major transits next April', "
                "'what were the outer planet movements during the Renaissance?'. "
                "Use offset to shift the window from today. "
                "Use extended=true for historical or far-future windows (outer planets only)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": (
                            "Number of days to scan. "
                            "Normal mode: default 30, max 365. "
                            "Extended mode: default 30, max 3650."
                        )
                    },
                    "future": {
                        "type": "boolean",
                        "description": "True = scan forward from today+offset (default), False = backward"
                    },
                    "offset": {
                        "type": "integer",
                        "description": (
                            "Days from today to start the scan window (default 0). "
                            "Normal mode: max 36500 (~100 years). "
                            "Extended mode: uncapped."
                        )
                    },
                    "extended": {
                        "type": "boolean",
                        "description": (
                            "If true, removes offset cap and raises scan cap to 3650 days, "
                            "but only returns outer planets (Jupiter through Pluto). "
                            "Inner planets are excluded in extended mode — they produce "
                            "thousands of events over long windows and become unreadable. "
                            "See docs/ARCHITECTURE.md for rationale and how to request changes."
                        )
                    }
                }
            }
        ),
    ]


# ============================================================================
# Handlers
# ============================================================================

async def handle_get_transits(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    try:
        engine = ctx.engine
        db = ctx.db
        
        date_str = arguments.get("date")
        time_str = arguments.get("time", "12:00")
        location_arg = arguments.get("location", "current")
        
        profile_id = arguments.get("profile_id")

        # Get profile — supplied or owner
        if profile_id is not None:
            profile = db.get_profile_by_id(profile_id)
            if not profile:
                return [TextContent(type="text", text=f"Error: Profile {profile_id} not found.")]
        else:
            profile = db.get_owner_profile()
            if not profile:
                return [TextContent(type="text", text="No owner profile configured. Run setup_owner first.")]
        
        # Resolve location
        #
        # Priority:
        #   1. Special keywords: current/home → current home location
        #   2. 'birth' → birth location
        #   3. Saved label match (case-insensitive)
        #   4. Geocode as an arbitrary city/place name (not saved)
        #
        # Ad-hoc geocoded locations are used for the ephemeris call but
        # never persisted — they won't appear in transit history location
        # labels unless the user explicitly saves them with add_location.

        location = None          # SQLAlchemy Location object (saved)
        adhoc_location = None    # dict for one-off geocoded locations

        if location_arg in ("current", "home"):
            location = db.get_current_home_location(profile)
            if not location:
                return [TextContent(type="text", text="No current home location set")]
        elif location_arg == "birth":
            location = db.get_birth_location(profile)
        else:
            # Try saved label first
            location = db.get_location_by_label(location_arg, profile)
            if not location:
                # Fall back to geocoding
                geo = geocode_location(location_arg)
                if geo:
                    adhoc_location = geo
                else:
                    return [TextContent(
                        type="text",
                        text=(
                            f"Location '{location_arg}' not found as a saved label "
                            f"and could not be geocoded. Try a more specific name "
                            f"(e.g. 'Bangkok, Thailand' or 'Seattle, WA')."
                        )
                    )]

        # Resolve lat/lon/label for the ephemeris call
        if adhoc_location:
            lat = adhoc_location["latitude"]
            lon = adhoc_location["longitude"]
            location_label = adhoc_location["name"].split(",")[0]  # short display name
        else:
            lat = location.latitude
            lon = location.longitude
            location_label = location.label
        
        # Get transits from ephemeris engine
        result = engine.get_chart(
            latitude=lat,
            longitude=lon,
            date_str=date_str,
            time_str=time_str,
            house_system_code='P'  # TODO: Get from profile
        )

        # AUTO-LOG: Save this transit lookup to database (saved locations only)
        # Ad-hoc geocoded locations are not persisted — log is skipped gracefully.
        try:
            if location:
                lookup_datetime = datetime.strptime(
                    f"{result['metadata']['date']} {result['metadata']['time']}",
                    "%Y-%m-%d %H:%M:%S"
                )
                db.save_transit_lookup(
                    profile=profile,
                    location=location,
                    lookup_datetime=lookup_datetime,
                    transit_data=result,
                    house_system_id=profile.preferred_house_system_id
                )
        except Exception as log_error:
            # Don't fail the entire request if logging fails
            print(f"Warning: Failed to log transit lookup: {log_error}")

        # Format response
        response = f"Transits for {result['metadata']['date']} at {result['metadata']['time']}\n"
        response += f"Location: {location_label} ({result['metadata']['latitude']}, {result['metadata']['longitude']})\n"
        response += f"House System: {result['metadata']['house_system']}\n\n"
        
        response += "Planets:\n"
        for planet, data in result['planets'].items():
            response += f"  {planet}: {data['degree']:.2f}° {data['sign']}\n"
        
        response += "\nHouses:\n"
        for house_num in sorted(result['houses'].keys(), key=lambda x: int(x)):
            data = result['houses'][house_num]
            response += f"  House {house_num}: {data['degree']:.2f}° {data['sign']}\n"
        
        if result['points']:
            response += "\nSpecial Points:\n"
            for point, data in result['points'].items():
                response += f"  {point}: {data['degree']:.2f}° {data['sign']}\n"
        
        return [TextContent(type="text", text=response)]
        
    except EphemerisError as e:
        return [TextContent(type="text", text=f"Ephemeris error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def handle_get_transit_history(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    try:
        db = ctx.db
        profile_id = arguments.get("profile_id")
        if profile_id is not None:
            profile = db.get_profile_by_id(profile_id)
            if not profile:
                return [TextContent(type="text", text=f"Error: Profile {profile_id} not found.")]
        else:
            profile = db.get_owner_profile()
            if not profile:
                return [TextContent(type="text", text="Error: Owner profile not configured. Run setup_owner first.")]

        after = arguments.get("after")
        before = arguments.get("before")
        planet = arguments.get("planet")
        sign = arguments.get("sign")
        limit = min(int(arguments.get("limit", 20)), 100)

        rows = db.get_transit_history(
            profile,
            after=after,
            before=before,
            planet=planet,
            sign=sign,
            limit=limit,
        )

        if not rows:
            filters = []
            if after:
                filters.append(f"after {after}")
            if before:
                filters.append(f"before {before}")
            if planet:
                filters.append(f"planet={planet}")
            if sign:
                filters.append(f"sign={sign}")
            filter_str = ", ".join(filters) if filters else "no filters"
            return [TextContent(
                type="text",
                text=f"No transit history found for {profile.name} ({filter_str})."
            )]

        # Format response
        response = f"# Transit History — {profile.name}\n"
        if after or before:
            date_range = f"{after or '...'} → {before or 'now'}"
            response += f"Date range: {date_range}\n"
        if planet:
            response += f"Planet filter: {planet}"
            if sign:
                response += f" in {sign}"
            response += "\n"
        response += f"Showing {len(rows)} lookup(s), newest first\n\n"

        PLANET_ORDER = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                        "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

        for row in rows:
            dt = row["lookup_datetime"].replace("T", " ")[:16]
            response += f"## {dt}  —  {row['location_label']}\n"

            planets_to_show = (
                {planet: row["planets"][planet]}
                if planet and planet in row["planets"]
                else row["planets"]
            )

            for pname in PLANET_ORDER:
                if pname not in planets_to_show:
                    continue
                pdata = planets_to_show[pname]
                retro = " ℞" if pdata.get("is_retrograde") else ""
                response += (
                    f"  {pname}: {pdata['degree']:.1f}° {pdata['sign']}{retro}\n"
                )
            response += "\n"

        return [TextContent(type="text", text=response)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def handle_find_last_transit(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    try:
        db = ctx.db
        profile_id = arguments.get("profile_id")
        if profile_id is not None:
            profile = db.get_profile_by_id(profile_id)
            if not profile:
                return [TextContent(type="text", text=f"Error: Profile {profile_id} not found.")]
        else:
            profile = db.get_owner_profile()
            if not profile:
                return [TextContent(type="text", text="Error: Owner profile not configured. Run setup_owner first.")]

        planet = arguments.get("planet")
        if not planet:
            return [TextContent(type="text", text="Error: 'planet' is required.")]

        sign = arguments.get("sign")
        retrograde = arguments.get("retrograde")  # None / True / False
        house = arguments.get("house")
        if house is not None:
            house = int(house)

        if sign is None and retrograde is None and house is None:
            return [TextContent(
                type="text",
                text="Error: Provide at least one filter: sign, retrograde, or house."
            )]

        result = db.find_last_transit(
            profile,
            planet=planet,
            sign=sign,
            retrograde=retrograde,
            house=house,
        )

        if result is None:
            conditions = []
            if sign:
                conditions.append(f"in {sign}")
            if retrograde is True:
                conditions.append("retrograde")
            elif retrograde is False:
                conditions.append("direct")
            if house:
                conditions.append(f"in house {house}")
            cond_str = " and ".join(conditions)
            return [TextContent(
                type="text",
                text=f"No logged transit found for {planet} {cond_str} in {profile.name}'s history."
            )]

        dt = result["lookup_datetime"].replace("T", " ")[:16]
        retro_str = " ℞ (retrograde)" if result["is_retrograde"] else ""
        house_str = f", House {result['house_number']}" if result["house_number"] else ""

        conditions = []
        if sign:
            conditions.append(f"in {sign}")
        if retrograde is True:
            conditions.append("retrograde")
        elif retrograde is False:
            conditions.append("direct")
        if house:
            conditions.append(f"in house {house}")
        cond_str = " and ".join(conditions)

        response = (
            f"# Last {planet} {cond_str}\n\n"
            f"**{dt}** — {result['location_label']}\n"
            f"{planet}: {result['degree']:.1f}° {result['sign']}{retro_str}{house_str}\n"
        )
        return [TextContent(type="text", text=response)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def handle_get_ingresses(ctx: ToolContext, arguments: Any) -> list[TextContent]:
    try:
        ephem_engine = ctx.engine
        db = ctx.db
        profile = db.get_owner_profile()
        if not profile:
            return [TextContent(type="text", text="Error: Owner profile not configured. Run setup_owner first.")]

        extended = bool(arguments.get("extended", False))
        days = int(arguments.get("days", 30))
        future = arguments.get("future", True)
        offset = int(arguments.get("offset", 0))

        events = db.get_ingresses(
            profile, ephem_engine,
            days=days, future=future,
            offset=offset, extended=extended,
        )

        direction_word = "Upcoming" if future else "Recent"
        offset_note = f", starting {offset} days from today" if offset else ""
        ext_note = " _(extended mode — outer planets only)_" if extended else ""
        response = (
            f"# {direction_word} Ingresses & Stations"
            f" — {days} days{offset_note}{ext_note}\n\n"
        )

        if not events:
            response += "No ingresses or stations found in this period.\n"
            return [TextContent(type="text", text=response)]

        # Group by month for readability
        from datetime import date
        current_month = None
        for event in events:
            month = event["date"][:7]  # YYYY-MM
            if month != current_month:
                d = date.fromisoformat(event["date"])
                response += f"## {d.strftime('%B %Y')}\n"
                current_month = month

            d = date.fromisoformat(event["date"])
            day_str = d.strftime("%b %-d")

            if event["event_type"] == "ingress":
                response += (
                    f"**{day_str}** — {event['planet']} {event['detail']} "
                    f"(from {event['from_sign']})\n"
                )
            else:  # station
                retro_symbol = " ℞" if event["is_retrograde"] else " D"
                response += (
                    f"**{day_str}** — {event['planet']}{retro_symbol} "
                    f"{event['detail']} in {event['sign']}\n"
                )

        response += f"\n_{len(events)} event(s) total_\n"
        return [TextContent(type="text", text=response)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


# ============================================================================
# Registration
# ============================================================================

def tool_specs() -> list[ToolSpec]:
    """The transit tools, in the order they are advertised."""
    return bind_handlers(
        get_transit_tools(),
        {
            "get_transits": handle_get_transits,
            "get_transit_history": handle_get_transit_history,
            "find_last_transit": handle_find_last_transit,
            "get_ingresses": handle_get_ingresses,
        },
    )
