"""The connection tools, called the way an AI client calls them: through `call_tool`.

Nothing of ours is mocked. Expected values are literals or come from an independent route (the
natal chart tool, or date arithmetic done here), never from the code under test.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tool_harness import add_owner, add_second


@pytest.fixture
def pair(tool):
    """Two profiles with natal charts stored, and a connection between them (ID 1)."""
    owner = add_owner(tool)
    other = add_second(tool)
    return owner, other


async def _make_pair_connection(tool, owner, other, **extra):
    return await tool("create_connection", {"label": "Pair", "profile_ids": [owner.id, other.id], **extra})


async def _store_natal_charts(tool, *profiles):
    for profile in profiles:
        await tool("get_natal_chart", {"profile_id": profile.id})


def _planet_lines(text: str) -> list[str]:
    """The '- **Sun**: ...' lines of a chart reply, in order."""
    return [line for line in text.splitlines() if line.startswith("- **") and "House" not in line][:10]


# -- create_connection -------------------------------------------------------------------------

async def test_create_connection_reports_what_was_saved(tool, pair):
    owner, other = pair
    text = await _make_pair_connection(tool, owner, other, type="romantic", start_date="2010-06-01")
    assert text == (
        "✓ Connection created!\n\n"
        "**Pair** (ID: 1)\n"
        "Type: romantic\n"
        "Since: 2010-06-01\n"
        "Members: Test Owner, Second Person\n\n"
        "Use get_connection_chart with connection_id=1 to calculate a chart."
    )


async def test_create_connection_without_optional_fields_omits_their_lines(tool, pair):
    owner, other = pair
    text = await _make_pair_connection(tool, owner, other)
    assert "Type:" not in text and "Since:" not in text


@pytest.mark.parametrize(
    "arguments, expected",
    [
        ({"profile_ids": [1, 2]}, "Error: label is required"),
        ({"label": "X", "profile_ids": [1]}, "Error: at least 2 profile_ids are required"),
        ({"label": "X", "profile_ids": [1, 99]}, "Error: Profile(s) 99 not found. Use list_profiles to see available profiles."),
    ],
)
async def test_create_connection_rejects_bad_input(tool, pair, arguments, expected):
    assert await tool("create_connection", arguments) == expected
    assert (await tool("list_connections")).startswith("No connections found.")


# -- list_connections --------------------------------------------------------------------------

async def test_list_connections_when_there_are_none(tool):
    assert await tool("list_connections") == "No connections found.\n\nUse create_connection to add one."


async def test_list_connections_shows_members_type_and_start_date(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other, type="romantic", start_date="2010-06-01")
    assert await tool("list_connections") == (
        "# Connections\n\n"
        "**Pair** (ID: 1)\n"
        "  Type: romantic\n"
        "  Members: Test Owner, Second Person\n"
        "  Since: 2010-06-01\n\n"
    )


# -- add_connection_member / remove_connection_member ------------------------------------------

async def test_add_member_joins_the_connection_and_clears_cached_charts(tool, pair):
    owner, other = pair
    third = add_second(tool, name="Third Person", date="1975-03-02", time="08:15")
    await _make_pair_connection(tool, owner, other)
    await _store_natal_charts(tool, owner, other, third)
    await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})
    assert "(cached)" in await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})

    reply = await tool("add_connection_member", {"connection_id": 1, "profile_id": third.id})

    assert reply == (
        "✓ Added **Third Person** to **Pair**.\n\n"
        "Cached charts have been invalidated. Use get_connection_chart to recalculate."
    )
    assert "Members: Test Owner, Second Person, Third Person" in await tool("list_connections")
    recalculated = await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})
    assert "(cached)" not in recalculated
    assert "Members: Test Owner, Second Person, Third Person" in recalculated


async def test_adding_an_existing_member_fails_and_changes_nothing(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)
    reply = await tool("add_connection_member", {"connection_id": 1, "profile_id": other.id})
    assert reply.startswith("Error adding member:")
    assert "already a member" in reply
    assert "[SQL:" not in reply and "IntegrityError" not in reply
    assert "Members: Test Owner, Second Person\n" in await tool("list_connections")


@pytest.mark.parametrize(
    "tool_name, arguments, expected",
    [
        ("add_connection_member", {"connection_id": 1}, "Error: connection_id and profile_id are required"),
        ("add_connection_member", {"connection_id": 9, "profile_id": 1}, "Error: connection 9 not found"),
        ("add_connection_member", {"connection_id": 1, "profile_id": 99}, "Error: Profile 99 not found. Use list_profiles to see available profiles."),
        ("remove_connection_member", {"connection_id": 1}, "Error: connection_id and profile_id are required"),
        ("remove_connection_member", {"connection_id": 9, "profile_id": 1}, "Error: connection 9 not found"),
        ("remove_connection_member", {"connection_id": 1, "profile_id": 99}, "Error: Profile 99 not found. Use list_profiles to see available profiles."),
    ],
)
async def test_member_tools_reject_bad_input(tool, pair, tool_name, arguments, expected):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)
    assert await tool(tool_name, arguments) == expected


async def test_remove_member_leaves_the_rest_in_place(tool, pair):
    owner, other = pair
    third = add_second(tool, name="Third Person", date="1975-03-02", time="08:15")
    await tool("create_connection", {"label": "Trio", "profile_ids": [owner.id, other.id, third.id]})

    reply = await tool("remove_connection_member", {"connection_id": 1, "profile_id": third.id})

    assert reply == "✓ Removed **Third Person** from **Trio**.\n\nCached charts have been invalidated."
    assert "Members: Test Owner, Second Person\n" in await tool("list_connections")


async def test_a_connection_keeps_at_least_two_members(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)
    reply = await tool("remove_connection_member", {"connection_id": 1, "profile_id": other.id})
    assert reply == (
        "Error: cannot remove Second Person — a connection must have at least 2 members.\n\n"
        "Use delete_connection to remove the whole connection instead."
    )
    assert "Members: Test Owner, Second Person\n" in await tool("list_connections")


# -- get_connection_chart: composite -----------------------------------------------------------

async def test_composite_needs_stored_natal_charts_first(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)
    reply = await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})
    assert reply == "Error: no natal chart data for Test Owner. Run get_natal_chart for this profile first."


async def test_composite_is_calculated_once_then_served_from_cache(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)
    await _store_natal_charts(tool, owner, other)

    first = await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})
    second = await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})
    forced = await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite", "invalidate": True})

    assert first.startswith("# Composite Chart — Pair\n\nMembers: Test Owner, Second Person\n")
    assert second.startswith("# Composite Chart — Pair (cached)\n")
    assert forced.startswith("# Composite Chart — Pair\n")           # recalculated, not cached
    for section in ("## Planets", "## Houses", "## Angles"):
        assert section in first and section in second
    assert len(_planet_lines(second)) == 10


async def test_composite_of_two_identical_charts_equals_that_chart(tool):
    """Averaging a chart with itself must give the same chart: an answer known without the code."""
    owner = add_owner(tool)
    twin = add_owner(tool, name="Twin")                    # same birth moment and place
    tool.db.set_owner_profile(owner.id)
    await tool("create_connection", {"label": "Twins", "profile_ids": [owner.id, twin.id]})
    natal = await tool("get_natal_chart", {"profile_id": owner.id})
    await tool("get_natal_chart", {"profile_id": twin.id})

    await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})
    composite = await tool("get_connection_chart", {"connection_id": 1, "chart_type": "composite"})

    planets = [line for line in natal.split("## House Cusps")[0].splitlines() if line.startswith("- **")]
    assert len(planets) == 10
    for line in planets:
        assert line in composite.splitlines(), f"composite differs from natal for {line}"


# -- get_connection_chart: Davison -------------------------------------------------------------

async def test_davison_chart_is_cast_at_the_midpoint_of_the_birth_moments(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)

    reply = await tool("get_connection_chart", {"connection_id": 1, "chart_type": "davison"})

    # The expected midpoint is worked out here from the two birth moments, in UT.
    born_a = datetime(1981, 5, 6, 0, 50, tzinfo=ZoneInfo("America/Chicago")).astimezone(timezone.utc)
    born_b = datetime(1990, 1, 15, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles")).astimezone(timezone.utc)
    midpoint = born_a + (born_b - born_a) / 2
    expected_when = (midpoint + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M")   # to the minute
    assert reply.startswith("# Davison Chart — Pair\n\nMembers: Test Owner, Second Person\n")
    assert f"Midpoint: {expected_when} UTC" in reply
    # Midpoint of the two birth places: mean latitude and longitude.
    assert "Location: 40.2773, -109.5310" in reply
    assert "(cached)" in await tool("get_connection_chart", {"connection_id": 1, "chart_type": "davison"})


# -- get_connection_chart: bad input -----------------------------------------------------------

@pytest.mark.parametrize(
    "arguments, expected",
    [
        ({"connection_id": 1}, "Error: connection_id and chart_type are required"),
        ({"chart_type": "composite"}, "Error: connection_id and chart_type are required"),
        ({"connection_id": 9, "chart_type": "composite"}, "Error: connection 9 not found"),
        ({"connection_id": 1, "chart_type": "synastry"}, "Error: unknown chart_type 'synastry'"),
    ],
)
async def test_connection_chart_rejects_bad_input(tool, pair, arguments, expected):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)
    assert await tool("get_connection_chart", arguments) == expected


# -- delete_connection -------------------------------------------------------------------------

async def test_delete_needs_explicit_confirmation(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)
    for arguments in ({"connection_id": 1}, {"connection_id": 1, "confirm": False}, {"connection_id": 1, "confirm": "yes"}):
        reply = await tool("delete_connection", arguments)
        assert reply.startswith("Error: set confirm=true to delete.")
    assert "**Pair** (ID: 1)" in await tool("list_connections")


async def test_delete_removes_the_connection_but_not_its_profiles(tool, pair):
    owner, other = pair
    await _make_pair_connection(tool, owner, other)

    reply = await tool("delete_connection", {"connection_id": 1, "confirm": True})

    assert reply == "✓ Connection **Pair** (ID: 1) deleted.\n\nMember profiles are unaffected."
    assert (await tool("list_connections")).startswith("No connections found.")
    profiles = await tool("list_profiles")
    assert "Test Owner" in profiles and "Second Person" in profiles


@pytest.mark.parametrize(
    "arguments, expected",
    [
        ({"confirm": True}, "Error: connection_id is required"),
        ({"connection_id": 9, "confirm": True}, "Error: connection 9 not found"),
    ],
)
async def test_delete_rejects_bad_input(tool, pair, arguments, expected):
    assert await tool("delete_connection", arguments) == expected
