"""The profile tools, called the way an AI client calls them: through `call_tool`.

Nothing of ours is mocked. Wording that is due to change with the unified error messages (not-found
cases, database errors) is matched loosely; the contract pinned is "it fails, says why, and changes
nothing". Known bugs are written as strict xfail tests that describe the correct behaviour, so the
fix has to remove the marker.
"""

import pytest

from tool_harness import add_owner

ALICE = {
    "name": "Alice",
    "birth_date": "1985-07-04",
    "birth_time": "14:30",
    "birth_location_name": "Austin, TX",
    "birth_latitude": 30.2672,
    "birth_longitude": -97.7431,
    "birth_timezone": "America/Chicago",
}


def assert_fails(reply: str, *fragments: str) -> None:
    assert reply.startswith("Error"), reply
    for fragment in fragments:
        assert fragment in reply, f"{fragment!r} missing from: {reply}"


# -- create_profile / list_profiles ------------------------------------------------------------

async def test_create_profile_reports_what_was_saved_and_offers_owner_setup(tool):
    reply = await tool("create_profile", ALICE)
    assert reply == (
        "✓ Profile created successfully!\n\n"
        "**Alice** (ID: 1)\n"
        "Born: 1985-07-04 at 14:30\n"
        "Location: Austin, TX\n"
        "Coordinates: 30.2672, -97.7431\n"
        "Timezone: America/Chicago\n\n"
        "Would you like to set this as your owner profile (i.e., 'you')?\n"
        "Use: setup_owner with profile_id=1"
    )


async def test_create_profile_needs_every_field(tool):
    assert_fails(await tool("create_profile", {"name": "Bob"}), "All fields are required")
    assert await tool("list_profiles") == "No profiles found in database.\n\nUse create_profile to add your first profile."


async def test_list_profiles_marks_the_owner(tool):
    await tool("create_profile", ALICE)
    await tool("create_profile", {**ALICE, "name": "Bob"})
    await tool("setup_owner", {"profile_id": 1})

    listing = await tool("list_profiles")

    assert "* **Alice** (ID: 1)" in listing
    assert "  **Bob** (ID: 2)" in listing
    assert "* Owner (you)" in listing


async def test_list_profiles_says_when_no_owner_is_set(tool):
    await tool("create_profile", ALICE)
    assert "No owner profile set. Use setup_owner to configure." in await tool("list_profiles")


# -- setup_owner -------------------------------------------------------------------------------

async def test_setup_owner_makes_that_profile_the_default_for_other_tools(tool):
    await tool("create_profile", ALICE)
    assert_fails(await tool("get_natal_chart"), "Owner profile not configured")

    reply = await tool("setup_owner", {"profile_id": 1})

    assert reply.startswith("✓ Owner profile set: **Alice** (ID: 1)\n\nBorn: 1985-07-04 at 14:30")
    assert (await tool("get_natal_chart")).startswith("# Natal Chart for 1985-07-04 at 14:30")


async def test_setup_owner_can_change_the_owner(tool):
    await tool("create_profile", ALICE)
    await tool("create_profile", {**ALICE, "name": "Bob", "birth_date": "1990-02-03"})
    await tool("setup_owner", {"profile_id": 1})
    await tool("setup_owner", {"profile_id": 2})
    assert (await tool("get_natal_chart")).startswith("# Natal Chart for 1990-02-03")


@pytest.mark.parametrize("arguments, fragments", [({}, ("profile_id is required",)), ({"profile_id": 9}, ("9", "not found"))])
async def test_setup_owner_rejects_bad_input(tool, arguments, fragments):
    assert_fails(await tool("setup_owner", arguments), *fragments)


# -- update_profile ----------------------------------------------------------------------------

async def test_update_name_keeps_the_stored_chart(tool):
    add_owner(tool)
    await tool("get_natal_chart")
    reply = await tool("update_profile", {"profile_id": 1, "field": "name", "value": "Renamed"})
    assert reply == "✓ Profile updated successfully!\n\n**Renamed** (ID: 1)\nUpdated field: name\nNew value: Renamed\n"
    assert "invalidated" not in reply


@pytest.mark.parametrize(
    "field, value, header",
    [
        ("birth_time", "15:00", "# Natal Chart for 1981-05-06 at 15:00"),
        ("birth_date", "1981-05-07", "# Natal Chart for 1981-05-07 at 00:50"),
    ],
)
async def test_changing_birth_data_makes_the_next_chart_use_the_new_data(tool, field, value, header):
    add_owner(tool)
    before = await tool("get_natal_chart")

    reply = await tool("update_profile", {"profile_id": 1, "field": field, "value": value})

    assert "natal chart cache invalidated" in reply
    after = await tool("get_natal_chart")
    assert after.startswith(header)
    assert after != before


async def test_update_profile_only_allows_name_and_birth_date_and_time(tool):
    add_owner(tool)
    assert await tool("update_profile", {"profile_id": 1, "field": "birth_timezone", "value": "UTC"}) == (
        "Error: Invalid field 'birth_timezone'. Must be one of: name, birth_date, birth_time"
    )


@pytest.mark.parametrize(
    "arguments, fragments",
    [
        ({"profile_id": 1}, ("Missing required fields",)),
        ({"profile_id": 9, "field": "name", "value": "Z"}, ("9", "not found")),
    ],
)
async def test_update_profile_rejects_bad_input(tool, arguments, fragments):
    add_owner(tool)
    assert_fails(await tool("update_profile", arguments), *fragments)


# -- add_location / remove_location ------------------------------------------------------------

async def test_add_location_saves_it_without_changing_home(tool):
    add_owner(tool)
    reply = await tool(
        "add_location",
        {"profile_id": 1, "label": "Work", "latitude": 40.7, "longitude": -74.0, "timezone": "America/New_York"},
    )
    assert reply.startswith("✓ Location added successfully!\n\n**Work** (ID: 2)\nProfile: Test Owner (ID: 1)")
    assert "Not set as home" in reply
    config = await tool("view_config")
    assert "- Birth (current home):" in config and "- Work: 40.7, -74.0" in config


async def test_add_location_can_make_it_the_current_home(tool):
    add_owner(tool)
    reply = await tool(
        "add_location",
        {"profile_id": 1, "label": "Beach", "latitude": 29.3, "longitude": -94.8, "timezone": "America/Chicago", "set_as_home": True},
    )
    assert "✓ Set as current home location for Test Owner" in reply
    config = await tool("view_config")
    assert "- Beach (current home): 29.3, -94.8" in config
    assert "- Birth (current home)" not in config


async def test_add_location_with_a_taken_label_fails_and_adds_nothing(tool):
    add_owner(tool)
    args = {"profile_id": 1, "label": "Work", "latitude": 40.7, "longitude": -74.0, "timezone": "America/New_York"}
    await tool("add_location", args)
    assert (await tool("add_location", {**args, "latitude": 1.0})).startswith("Error adding location:")
    assert (await tool("view_config")).count("- Work:") == 1


@pytest.mark.parametrize(
    "arguments, fragments",
    [
        ({"profile_id": 1}, ("Missing required fields",)),
        ({"profile_id": 9, "label": "L", "latitude": 1, "longitude": 1, "timezone": "UTC"}, ("9", "not found")),
    ],
)
async def test_add_location_rejects_bad_input(tool, arguments, fragments):
    add_owner(tool)
    assert_fails(await tool("add_location", arguments), *fragments)


async def test_remove_location_deletes_a_saved_place(tool):
    add_owner(tool)
    await tool("add_location", {"profile_id": 1, "label": "Work", "latitude": 40.7, "longitude": -74.0, "timezone": "America/New_York"})
    reply = await tool("remove_location", {"location_id": 2})
    assert reply == "✓ Location removed successfully!\n\nDeleted: **Work** (ID: 2)\nCoordinates: 40.7, -74.0"
    assert "- Work" not in await tool("view_config")


async def test_the_birth_location_cannot_be_removed(tool):
    add_owner(tool)
    reply = await tool("remove_location", {"location_id": 1})
    assert_fails(reply, "birth location")
    assert "- Birth (current home)" in await tool("view_config")


@pytest.mark.parametrize("arguments, fragments", [({}, ("location_id is required",)), ({"location_id": 99}, ("99", "not found"))])
async def test_remove_location_rejects_bad_input(tool, arguments, fragments):
    assert_fails(await tool("remove_location", arguments), *fragments)


# -- delete_profile ----------------------------------------------------------------------------

async def test_delete_profile_needs_explicit_confirmation(tool):
    add_owner(tool)
    for arguments in ({"profile_id": 1}, {"profile_id": 1, "confirm": False}):
        assert_fails(await tool("delete_profile", arguments), "confirm=true")
    assert "Test Owner" in await tool("list_profiles")


async def test_delete_profile_removes_it_and_its_places(tool):
    add_owner(tool)
    other = await tool("create_profile", ALICE)
    assert "ID: 2" in other

    reply = await tool("delete_profile", {"profile_id": 2, "confirm": True})

    assert reply.startswith("✓ Profile deleted permanently!\n\nDeleted: **Alice** (ID: 2)")
    listing = await tool("list_profiles")
    assert "Alice" not in listing and "Test Owner" in listing
    assert "Austin" not in await tool("view_config")


@pytest.mark.parametrize("arguments, fragments", [({"confirm": True}, ("profile_id is required",)), ({"profile_id": 99, "confirm": True}, ("99", "not found"))])
async def test_delete_profile_rejects_bad_input(tool, arguments, fragments):
    assert_fails(await tool("delete_profile", arguments), *fragments)


# -- known bugs: strict xfail, written as the behaviour we want ----------------------------------

INVALID_PROFILE_FIELDS = [
    ("birth_timezone", "Mars/Base"),
    ("birth_date", "1985-13-45"),
    ("birth_time", "25:99"),
    ("birth_latitude", 123),
]


@pytest.mark.parametrize("field, value", INVALID_PROFILE_FIELDS)
async def test_create_profile_rejects_invalid_values(tool, field, value):
    assert_fails(await tool("create_profile", {**ALICE, field: value}))
    assert (await tool("list_profiles")).startswith("No profiles found")


@pytest.mark.parametrize("field, value", [("birth_date", "nope"), ("birth_time", "99:99")])
async def test_update_profile_rejects_an_invalid_date_or_time(tool, field, value):
    add_owner(tool)
    assert_fails(await tool("update_profile", {"profile_id": 1, "field": field, "value": value}))
    assert value not in await tool("list_profiles")


async def test_add_location_rejects_an_unknown_timezone(tool):
    add_owner(tool)
    reply = await tool(
        "add_location",
        {"profile_id": 1, "label": "Bad", "latitude": 1, "longitude": 1, "timezone": "Mars/Base"},
    )
    assert_fails(reply)


async def test_a_taken_location_label_does_not_show_database_internals(tool):
    add_owner(tool)
    args = {"profile_id": 1, "label": "Work", "latitude": 40.7, "longitude": -74.0, "timezone": "America/New_York"}
    await tool("add_location", args)
    reply = await tool("add_location", args)
    assert "[SQL:" not in reply and "IntegrityError" not in reply
