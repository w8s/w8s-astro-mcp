"""Tests for profile management MCP tools."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from w8s_astro_mcp.tools.profile_management import (
    handle_list_profiles,
    handle_set_current_profile,
    handle_create_profile,
    handle_add_location,
    handle_update_profile,
    handle_remove_location,
)
from w8s_astro_mcp.models.profile import Profile
from w8s_astro_mcp.models.location import Location


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_helper():
    """Create a mock DatabaseHelper."""
    return Mock()


@pytest.fixture
def sample_profile_1():
    """Create a sample profile (Todd)."""
    profile = Profile(
        id=1,
        name="Todd Waits",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_id=1,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return profile


@pytest.fixture
def sample_profile_2():
    """Create a sample profile (Sarah)."""
    profile = Profile(
        id=2,
        name="Sarah Johnson",
        birth_date="1985-03-15",
        birth_time="14:30",
        birth_location_id=2,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return profile


@pytest.fixture
def sample_location_1():
    """Create a sample birth location."""
    location = Location(
        id=1,
        profile_id=1,
        label="Birth",
        latitude=32.9483,
        longitude=-96.7297,
        timezone="America/Chicago",
        is_current_home=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return location


@pytest.fixture
def sample_location_2():
    """Create a sample birth location."""
    location = Location(
        id=2,
        profile_id=2,
        label="Birth",
        latitude=40.7128,
        longitude=-74.0060,
        timezone="America/New_York",
        is_current_home=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return location


# ============================================================================
# Tests for list_profiles
# ============================================================================

@pytest.mark.asyncio
async def test_list_profiles_empty_database(mock_db_helper):
    """Test list_profiles with no profiles in database."""
    # Setup
    mock_db_helper.list_all_profiles.return_value = []
    mock_db_helper.get_current_profile.return_value = None
    
    # Execute
    result = await handle_list_profiles(mock_db_helper)
    
    # Assert
    assert len(result) == 1
    assert result[0].type == "text"
    assert "No profiles found" in result[0].text
    assert "create_profile" in result[0].text


@pytest.mark.asyncio
async def test_list_profiles_single_profile(mock_db_helper, sample_profile_1, sample_location_1):
    """Test list_profiles with one profile."""
    # Setup
    mock_db_helper.list_all_profiles.return_value = [sample_profile_1]
    mock_db_helper.get_current_profile.return_value = sample_profile_1
    mock_db_helper.get_birth_location.return_value = sample_location_1
    
    # Execute
    result = await handle_list_profiles(mock_db_helper)
    
    # Assert
    assert len(result) == 1
    assert result[0].type == "text"
    text = result[0].text
    
    # Check profile info present
    assert "Todd Waits" in text
    assert "ID: 1" in text
    assert "1981-05-06" in text
    assert "00:50" in text
    assert "Birth" in text  # Location label
    
    # Check current profile indicator
    assert "* " in text or "*" in text  # Current profile marker
    assert "current active profile" in text.lower()


@pytest.mark.asyncio
async def test_list_profiles_multiple_profiles(
    mock_db_helper, 
    sample_profile_1, 
    sample_profile_2,
    sample_location_1,
    sample_location_2
):
    """Test list_profiles with multiple profiles."""
    # Setup
    mock_db_helper.list_all_profiles.return_value = [sample_profile_1, sample_profile_2]
    mock_db_helper.get_current_profile.return_value = sample_profile_1  # Todd is current
    
    # Mock birth location calls
    def get_birth_location_side_effect(profile):
        if profile.id == 1:
            return sample_location_1
        elif profile.id == 2:
            return sample_location_2
        return None
    
    mock_db_helper.get_birth_location.side_effect = get_birth_location_side_effect
    
    # Execute
    result = await handle_list_profiles(mock_db_helper)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    # Check both profiles present
    assert "Todd Waits" in text
    assert "Sarah Johnson" in text
    assert "ID: 1" in text
    assert "ID: 2" in text
    
    # Check current profile indicator (only on Todd)
    lines = text.split('\n')
    todd_lines = [l for l in lines if "Todd Waits" in l]
    sarah_lines = [l for l in lines if "Sarah Johnson" in l]
    
    assert len(todd_lines) > 0
    assert len(sarah_lines) > 0
    
    # Todd should have the current indicator
    assert any("*" in line for line in todd_lines)


@pytest.mark.asyncio
async def test_list_profiles_no_current_profile(mock_db_helper, sample_profile_1):
    """Test list_profiles when no current profile is set."""
    # Setup
    mock_db_helper.list_all_profiles.return_value = [sample_profile_1]
    mock_db_helper.get_current_profile.return_value = None
    mock_db_helper.get_birth_location.return_value = None
    
    # Execute
    result = await handle_list_profiles(mock_db_helper)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Todd Waits" in text
    assert "No current profile set" in text or "set_current_profile" in text


@pytest.mark.asyncio
async def test_list_profiles_error_handling(mock_db_helper):
    """Test list_profiles handles database errors gracefully."""
    # Setup - simulate database error
    mock_db_helper.list_all_profiles.side_effect = Exception("Database connection failed")
    
    # Execute
    result = await handle_list_profiles(mock_db_helper)
    
    # Assert
    assert len(result) == 1
    assert "Error listing profiles" in result[0].text
    assert "Database connection failed" in result[0].text


# ============================================================================
# Tests for set_current_profile
# ============================================================================

@pytest.mark.asyncio
async def test_set_current_profile_success(mock_db_helper, sample_profile_1):
    """Test set_current_profile with valid profile ID."""
    # Setup
    mock_db_helper.set_current_profile.return_value = True
    mock_db_helper.get_profile_by_id.return_value = sample_profile_1
    
    # Execute
    result = await handle_set_current_profile(mock_db_helper, {"profile_id": 1})
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "Todd Waits" in text
    assert "ID: 1" in text
    assert "1981-05-06" in text
    assert "get_natal_chart" in text  # Should mention what this affects
    
    # Verify method called correctly
    mock_db_helper.set_current_profile.assert_called_once_with(1)
    mock_db_helper.get_profile_by_id.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_set_current_profile_invalid_id(mock_db_helper):
    """Test set_current_profile with non-existent profile ID."""
    # Setup
    mock_db_helper.set_current_profile.return_value = False
    
    # Execute
    result = await handle_set_current_profile(mock_db_helper, {"profile_id": 999})
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text or "not found" in text.lower()
    assert "999" in text
    assert "list_profiles" in text  # Should suggest using list_profiles
    
    # Verify method called
    mock_db_helper.set_current_profile.assert_called_once_with(999)
    # Should NOT call get_profile_by_id since it failed
    mock_db_helper.get_profile_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_set_current_profile_missing_parameter(mock_db_helper):
    """Test set_current_profile with missing profile_id parameter."""
    # Execute
    result = await handle_set_current_profile(mock_db_helper, {})
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "profile_id is required" in text
    
    # Should not call database
    mock_db_helper.set_current_profile.assert_not_called()


@pytest.mark.asyncio
async def test_set_current_profile_none_parameter(mock_db_helper):
    """Test set_current_profile with None as profile_id."""
    # Execute
    result = await handle_set_current_profile(mock_db_helper, {"profile_id": None})
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "profile_id is required" in text


@pytest.mark.asyncio
async def test_set_current_profile_error_handling(mock_db_helper):
    """Test set_current_profile handles database errors gracefully."""
    # Setup - simulate database error
    mock_db_helper.set_current_profile.side_effect = Exception("Database error")
    
    # Execute
    result = await handle_set_current_profile(mock_db_helper, {"profile_id": 1})
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error setting current profile" in text
    assert "Database error" in text


# ============================================================================
# Integration-style tests (using both functions together)
# ============================================================================

@pytest.mark.asyncio
async def test_workflow_list_then_set(
    mock_db_helper,
    sample_profile_1,
    sample_profile_2,
    sample_location_1,
    sample_location_2
):
    """Test realistic workflow: list profiles, then set one as current."""
    # Setup for list_profiles
    mock_db_helper.list_all_profiles.return_value = [sample_profile_1, sample_profile_2]
    mock_db_helper.get_current_profile.return_value = sample_profile_1
    
    def get_birth_location_side_effect(profile):
        if profile.id == 1:
            return sample_location_1
        elif profile.id == 2:
            return sample_location_2
        return None
    
    mock_db_helper.get_birth_location.side_effect = get_birth_location_side_effect
    
    # Step 1: List profiles
    list_result = await handle_list_profiles(mock_db_helper)
    assert "Todd Waits" in list_result[0].text
    assert "Sarah Johnson" in list_result[0].text
    
    # Setup for set_current_profile
    mock_db_helper.set_current_profile.return_value = True
    mock_db_helper.get_profile_by_id.return_value = sample_profile_2
    
    # Step 2: Set Sarah as current
    set_result = await handle_set_current_profile(mock_db_helper, {"profile_id": 2})
    assert "Sarah Johnson" in set_result[0].text
    
    # Verify the switch happened
    mock_db_helper.set_current_profile.assert_called_with(2)


# ============================================================================
# Tests for create_profile
# ============================================================================

@pytest.mark.asyncio
async def test_create_profile_success(mock_db_helper, sample_profile_2):
    """Test create_profile with valid data."""
    # Setup
    mock_db_helper.create_profile_with_location.return_value = sample_profile_2
    
    arguments = {
        "name": "Sarah Johnson",
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_latitude": 40.7128,
        "birth_longitude": -74.0060,
        "birth_timezone": "America/New_York"
    }
    
    # Execute
    result = await handle_create_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    # Check success indicator and profile info
    assert "✓" in text or "success" in text.lower()
    assert "Sarah Johnson" in text
    assert "ID: 2" in text
    assert "1985-03-15" in text
    assert "14:30" in text
    assert "New York, NY" in text
    assert "40.7128" in text
    assert "-74.006" in text
    assert "America/New_York" in text
    
    # Should prompt about setting as current
    assert "set_current_profile" in text.lower() or "current profile" in text.lower()
    
    # Verify database method called correctly
    mock_db_helper.create_profile_with_location.assert_called_once_with(
        name="Sarah Johnson",
        birth_date="1985-03-15",
        birth_time="14:30",
        birth_location_name="New York, NY",
        birth_latitude=40.7128,
        birth_longitude=-74.0060,
        birth_timezone="America/New_York"
    )


@pytest.mark.asyncio
async def test_create_profile_missing_name(mock_db_helper):
    """Test create_profile with missing name field."""
    arguments = {
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_latitude": 40.7128,
        "birth_longitude": -74.0060,
        "birth_timezone": "America/New_York"
    }
    
    # Execute
    result = await handle_create_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "required" in text.lower()
    
    # Should NOT call database
    mock_db_helper.create_profile_with_location.assert_not_called()


@pytest.mark.asyncio
async def test_create_profile_missing_coordinates(mock_db_helper):
    """Test create_profile with missing latitude."""
    arguments = {
        "name": "Sarah Johnson",
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_longitude": -74.0060,
        "birth_timezone": "America/New_York"
    }
    
    # Execute
    result = await handle_create_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "required" in text.lower()
    
    # Should NOT call database
    mock_db_helper.create_profile_with_location.assert_not_called()


@pytest.mark.asyncio
async def test_create_profile_missing_timezone(mock_db_helper):
    """Test create_profile with missing timezone."""
    arguments = {
        "name": "Sarah Johnson",
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_latitude": 40.7128,
        "birth_longitude": -74.0060
    }
    
    # Execute
    result = await handle_create_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "required" in text.lower()


@pytest.mark.asyncio
async def test_create_profile_error_handling(mock_db_helper):
    """Test create_profile handles database errors gracefully."""
    # Setup - simulate database error
    mock_db_helper.create_profile_with_location.side_effect = Exception("Database constraint violation")
    
    arguments = {
        "name": "Sarah Johnson",
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_latitude": 40.7128,
        "birth_longitude": -74.0060,
        "birth_timezone": "America/New_York"
    }
    
    # Execute
    result = await handle_create_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error creating profile" in text
    assert "Database constraint violation" in text


@pytest.mark.asyncio
async def test_create_profile_duplicate_name_allowed(mock_db_helper, sample_profile_1):
    """Test that duplicate names are allowed (profiles distinguished by ID)."""
    # Setup - create a profile with same name as existing one
    new_profile = Profile(
        id=3,
        name="Todd Waits",  # Same name as sample_profile_1
        birth_date="1990-01-01",
        birth_time="12:00",
        birth_location_id=5,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.create_profile_with_location.return_value = new_profile
    
    arguments = {
        "name": "Todd Waits",
        "birth_date": "1990-01-01",
        "birth_time": "12:00",
        "birth_location_name": "Chicago, IL",
        "birth_latitude": 41.8781,
        "birth_longitude": -87.6298,
        "birth_timezone": "America/Chicago"
    }
    
    # Execute
    result = await handle_create_profile(mock_db_helper, arguments)
    
    # Assert - should succeed
    assert len(result) == 1
    text = result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "Todd Waits" in text
    assert "ID: 3" in text  # Different ID even though same name


@pytest.mark.asyncio
async def test_workflow_create_then_list(mock_db_helper, sample_profile_1, sample_profile_2, sample_location_1, sample_location_2):
    """Test realistic workflow: create profile, then list to see it."""
    # Step 1: Create profile
    mock_db_helper.create_profile_with_location.return_value = sample_profile_2
    
    arguments = {
        "name": "Sarah Johnson",
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_latitude": 40.7128,
        "birth_longitude": -74.0060,
        "birth_timezone": "America/New_York"
    }
    
    create_result = await handle_create_profile(mock_db_helper, arguments)
    assert "Sarah Johnson" in create_result[0].text
    assert "ID: 2" in create_result[0].text
    
    # Step 2: List profiles - should show both profiles now
    mock_db_helper.list_all_profiles.return_value = [sample_profile_1, sample_profile_2]
    mock_db_helper.get_current_profile.return_value = sample_profile_1
    
    def get_birth_location_side_effect(profile):
        if profile.id == 1:
            return sample_location_1
        elif profile.id == 2:
            return sample_location_2
        return None
    
    mock_db_helper.get_birth_location.side_effect = get_birth_location_side_effect
    
    list_result = await handle_list_profiles(mock_db_helper)
    text = list_result[0].text
    
    # Both profiles should appear
    assert "Todd Waits" in text
    assert "Sarah Johnson" in text
    assert "ID: 1" in text
    assert "ID: 2" in text


# ============================================================================
# Tests for add_location
# ============================================================================

@pytest.mark.asyncio
async def test_add_location_success(mock_db_helper, sample_profile_1):
    """Test add_location with valid data."""
    # Setup
    mock_db_helper.get_profile_by_id.return_value = sample_profile_1
    
    new_location = Location(
        id=10,
        profile_id=1,
        label="Office",
        latitude=32.7800,
        longitude=-96.8000,
        timezone="America/Chicago",
        is_current_home=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.create_location.return_value = new_location
    
    arguments = {
        "profile_id": 1,
        "label": "Office",
        "latitude": 32.7800,
        "longitude": -96.8000,
        "timezone": "America/Chicago",
        "set_as_home": False
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    # Check success indicator and location info
    assert "✓" in text or "success" in text.lower()
    assert "Office" in text
    assert "ID: 10" in text
    assert "Todd Waits" in text
    assert "32.78" in text or "32.8" in text
    assert "-96.8" in text
    assert "America/Chicago" in text
    assert "Not set as home" in text or "set_as_home=true" in text
    
    # Verify database methods called correctly
    mock_db_helper.get_profile_by_id.assert_called_once_with(1)
    mock_db_helper.create_location.assert_called_once_with(
        profile_id=1,
        label="Office",
        latitude=32.7800,
        longitude=-96.8000,
        timezone="America/Chicago",
        set_as_home=False
    )


@pytest.mark.asyncio
async def test_add_location_set_as_home(mock_db_helper, sample_profile_1):
    """Test add_location with set_as_home=True."""
    # Setup
    mock_db_helper.get_profile_by_id.return_value = sample_profile_1
    
    new_location = Location(
        id=11,
        profile_id=1,
        label="Paris Vacation",
        latitude=48.8566,
        longitude=2.3522,
        timezone="Europe/Paris",
        is_current_home=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.create_location.return_value = new_location
    
    arguments = {
        "profile_id": 1,
        "label": "Paris Vacation",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "timezone": "Europe/Paris",
        "set_as_home": True
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "Paris Vacation" in text
    assert "Set as current home" in text or "home location" in text.lower()
    assert "Todd Waits" in text
    
    # Verify set_as_home was passed correctly
    mock_db_helper.create_location.assert_called_once_with(
        profile_id=1,
        label="Paris Vacation",
        latitude=48.8566,
        longitude=2.3522,
        timezone="Europe/Paris",
        set_as_home=True
    )


@pytest.mark.asyncio
async def test_add_location_missing_profile_id(mock_db_helper):
    """Test add_location with missing profile_id."""
    arguments = {
        "label": "Office",
        "latitude": 32.7800,
        "longitude": -96.8000,
        "timezone": "America/Chicago"
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "required" in text.lower()
    
    # Should NOT call database
    mock_db_helper.get_profile_by_id.assert_not_called()
    mock_db_helper.create_location.assert_not_called()


@pytest.mark.asyncio
async def test_add_location_missing_label(mock_db_helper):
    """Test add_location with missing label."""
    arguments = {
        "profile_id": 1,
        "latitude": 32.7800,
        "longitude": -96.8000,
        "timezone": "America/Chicago"
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "required" in text.lower()
    
    # Should NOT call database
    mock_db_helper.create_location.assert_not_called()


@pytest.mark.asyncio
async def test_add_location_missing_coordinates(mock_db_helper):
    """Test add_location with missing latitude."""
    arguments = {
        "profile_id": 1,
        "label": "Office",
        "longitude": -96.8000,
        "timezone": "America/Chicago"
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "required" in text.lower()


@pytest.mark.asyncio
async def test_add_location_profile_not_found(mock_db_helper):
    """Test add_location when profile doesn't exist."""
    # Setup
    mock_db_helper.get_profile_by_id.return_value = None
    
    arguments = {
        "profile_id": 999,
        "label": "Office",
        "latitude": 32.7800,
        "longitude": -96.8000,
        "timezone": "America/Chicago"
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "999" in text
    assert "not found" in text.lower()
    assert "list_profiles" in text
    
    # Should check profile but NOT create location
    mock_db_helper.get_profile_by_id.assert_called_once_with(999)
    mock_db_helper.create_location.assert_not_called()


@pytest.mark.asyncio
async def test_add_location_database_error(mock_db_helper, sample_profile_1):
    """Test add_location handles database errors gracefully."""
    # Setup
    mock_db_helper.get_profile_by_id.return_value = sample_profile_1
    mock_db_helper.create_location.side_effect = ValueError("Profile 1 not found")
    
    arguments = {
        "profile_id": 1,
        "label": "Office",
        "latitude": 32.7800,
        "longitude": -96.8000,
        "timezone": "America/Chicago"
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "Profile 1 not found" in text
    assert "list_profiles" in text


@pytest.mark.asyncio
async def test_add_location_default_set_as_home_false(mock_db_helper, sample_profile_1):
    """Test that set_as_home defaults to False when not provided."""
    # Setup
    mock_db_helper.get_profile_by_id.return_value = sample_profile_1
    
    new_location = Location(
        id=12,
        profile_id=1,
        label="Temporary",
        latitude=30.0,
        longitude=-90.0,
        timezone="America/Chicago",
        is_current_home=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.create_location.return_value = new_location
    
    # Note: set_as_home not in arguments
    arguments = {
        "profile_id": 1,
        "label": "Temporary",
        "latitude": 30.0,
        "longitude": -90.0,
        "timezone": "America/Chicago"
    }
    
    # Execute
    result = await handle_add_location(mock_db_helper, arguments)
    
    # Assert
    text = result[0].text
    assert "✓" in text or "success" in text.lower()
    
    # Verify set_as_home defaulted to False
    mock_db_helper.create_location.assert_called_once_with(
        profile_id=1,
        label="Temporary",
        latitude=30.0,
        longitude=-90.0,
        timezone="America/Chicago",
        set_as_home=False  # Should default to False
    )


@pytest.mark.asyncio
async def test_workflow_create_profile_then_add_location(mock_db_helper, sample_profile_2):
    """Test workflow: create profile, then add location."""
    # Step 1: Create profile
    mock_db_helper.create_profile_with_location.return_value = sample_profile_2
    
    create_args = {
        "name": "Sarah Johnson",
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_latitude": 40.7128,
        "birth_longitude": -74.0060,
        "birth_timezone": "America/New_York"
    }
    
    create_result = await handle_create_profile(mock_db_helper, create_args)
    assert "Sarah Johnson" in create_result[0].text
    assert "ID: 2" in create_result[0].text
    
    # Step 2: Add location to the new profile
    mock_db_helper.get_profile_by_id.return_value = sample_profile_2
    
    new_location = Location(
        id=20,
        profile_id=2,
        label="Work",
        latitude=40.7580,
        longitude=-73.9855,
        timezone="America/New_York",
        is_current_home=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.create_location.return_value = new_location
    
    location_args = {
        "profile_id": 2,
        "label": "Work",
        "latitude": 40.7580,
        "longitude": -73.9855,
        "timezone": "America/New_York",
        "set_as_home": False
    }
    
    location_result = await handle_add_location(mock_db_helper, location_args)
    text = location_result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "Work" in text
    assert "Sarah Johnson" in text  # Shows profile name
    
    # Verify both operations completed
    mock_db_helper.create_profile_with_location.assert_called_once()
    mock_db_helper.create_location.assert_called_once()


# ============================================================================
# Tests for update_profile
# ============================================================================

@pytest.mark.asyncio
async def test_update_profile_name_success(mock_db_helper, sample_profile_1):
    """Test update_profile with name field."""
    # Setup - create updated profile
    updated_profile = Profile(
        id=1,
        name="Todd M. Waits",  # Updated name
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_id=1,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.update_profile_field.return_value = updated_profile
    
    arguments = {
        "profile_id": 1,
        "field": "name",
        "value": "Todd M. Waits"
    }
    
    # Execute
    result = await handle_update_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "Todd M. Waits" in text
    assert "ID: 1" in text
    assert "Updated field: name" in text
    assert "New value: Todd M. Waits" in text
    
    # Should NOT mention natal cache for name changes
    assert "natal" not in text.lower() or "cache" not in text.lower()
    
    # Verify database method called correctly
    mock_db_helper.update_profile_field.assert_called_once_with(1, "name", "Todd M. Waits")


@pytest.mark.asyncio
async def test_update_profile_birth_date_invalidates_cache(mock_db_helper, sample_profile_1):
    """Test update_profile with birth_date field invalidates natal cache."""
    # Setup
    updated_profile = Profile(
        id=1,
        name="Todd Waits",
        birth_date="1981-05-07",  # Updated birth date
        birth_time="00:50",
        birth_location_id=1,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.update_profile_field.return_value = updated_profile
    
    arguments = {
        "profile_id": 1,
        "field": "birth_date",
        "value": "1981-05-07"
    }
    
    # Execute
    result = await handle_update_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "1981-05-07" in text
    assert "Updated field: birth_date" in text
    
    # MUST mention natal cache invalidation
    assert "natal" in text.lower()
    assert "cache" in text.lower()
    assert "invalidate" in text.lower() or "recalculate" in text.lower()
    
    mock_db_helper.update_profile_field.assert_called_once_with(1, "birth_date", "1981-05-07")


@pytest.mark.asyncio
async def test_update_profile_birth_time_invalidates_cache(mock_db_helper, sample_profile_1):
    """Test update_profile with birth_time field invalidates natal cache."""
    # Setup
    updated_profile = Profile(
        id=1,
        name="Todd Waits",
        birth_date="1981-05-06",
        birth_time="01:00",  # Updated birth time
        birth_location_id=1,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.update_profile_field.return_value = updated_profile
    
    arguments = {
        "profile_id": 1,
        "field": "birth_time",
        "value": "01:00"
    }
    
    # Execute
    result = await handle_update_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "01:00" in text
    assert "Updated field: birth_time" in text
    
    # MUST mention natal cache invalidation
    assert "natal" in text.lower()
    assert "cache" in text.lower()
    
    mock_db_helper.update_profile_field.assert_called_once_with(1, "birth_time", "01:00")


@pytest.mark.asyncio
async def test_update_profile_missing_parameters(mock_db_helper):
    """Test update_profile with missing parameters."""
    # Missing field
    result1 = await handle_update_profile(mock_db_helper, {
        "profile_id": 1,
        "value": "test"
    })
    assert "Error" in result1[0].text
    assert "required" in result1[0].text.lower()
    
    # Missing value
    result2 = await handle_update_profile(mock_db_helper, {
        "profile_id": 1,
        "field": "name"
    })
    assert "Error" in result2[0].text
    assert "required" in result2[0].text.lower()
    
    # Missing profile_id
    result3 = await handle_update_profile(mock_db_helper, {
        "field": "name",
        "value": "test"
    })
    assert "Error" in result3[0].text
    assert "required" in result3[0].text.lower()
    
    # Should NOT call database
    mock_db_helper.update_profile_field.assert_not_called()


@pytest.mark.asyncio
async def test_update_profile_invalid_field(mock_db_helper):
    """Test update_profile with invalid field name."""
    # Setup - database helper raises ValueError
    mock_db_helper.update_profile_field.side_effect = ValueError(
        "Invalid field 'invalid_field'. Must be one of: name, birth_date, birth_time"
    )
    
    arguments = {
        "profile_id": 1,
        "field": "invalid_field",
        "value": "test"
    }
    
    # Execute
    result = await handle_update_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "Invalid field" in text
    assert "invalid_field" in text
    
    mock_db_helper.update_profile_field.assert_called_once_with(1, "invalid_field", "test")


@pytest.mark.asyncio
async def test_update_profile_profile_not_found(mock_db_helper):
    """Test update_profile when profile doesn't exist."""
    # Setup - database helper raises ValueError
    mock_db_helper.update_profile_field.side_effect = ValueError("Profile 999 not found")
    
    arguments = {
        "profile_id": 999,
        "field": "name",
        "value": "test"
    }
    
    # Execute
    result = await handle_update_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "999" in text
    assert "not found" in text.lower()
    
    mock_db_helper.update_profile_field.assert_called_once_with(999, "name", "test")


@pytest.mark.asyncio
async def test_update_profile_error_handling(mock_db_helper):
    """Test update_profile handles unexpected errors gracefully."""
    # Setup - simulate unexpected database error
    mock_db_helper.update_profile_field.side_effect = Exception("Database connection lost")
    
    arguments = {
        "profile_id": 1,
        "field": "name",
        "value": "test"
    }
    
    # Execute
    result = await handle_update_profile(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error updating profile" in text
    assert "Database connection lost" in text


@pytest.mark.asyncio
async def test_workflow_create_update_list(mock_db_helper, sample_profile_2, sample_location_1, sample_location_2):
    """Test workflow: create profile, update it, then list to see changes."""
    # Step 1: Create profile
    mock_db_helper.create_profile_with_location.return_value = sample_profile_2
    
    create_args = {
        "name": "Sarah Johnson",
        "birth_date": "1985-03-15",
        "birth_time": "14:30",
        "birth_location_name": "New York, NY",
        "birth_latitude": 40.7128,
        "birth_longitude": -74.0060,
        "birth_timezone": "America/New_York"
    }
    
    create_result = await handle_create_profile(mock_db_helper, create_args)
    assert "Sarah Johnson" in create_result[0].text
    
    # Step 2: Update profile name
    updated_profile = Profile(
        id=2,
        name="Sarah Marie Johnson",  # Updated
        birth_date="1985-03-15",
        birth_time="14:30",
        birth_location_id=2,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.update_profile_field.return_value = updated_profile
    
    update_args = {
        "profile_id": 2,
        "field": "name",
        "value": "Sarah Marie Johnson"
    }
    
    update_result = await handle_update_profile(mock_db_helper, update_args)
    assert "Sarah Marie Johnson" in update_result[0].text
    
    # Step 3: List profiles - should show updated name
    sample_profile_1_for_list = Profile(
        id=1,
        name="Todd Waits",
        birth_date="1981-05-06",
        birth_time="00:50",
        birth_location_id=1,
        preferred_house_system_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    mock_db_helper.list_all_profiles.return_value = [sample_profile_1_for_list, updated_profile]
    mock_db_helper.get_current_profile.return_value = sample_profile_1_for_list
    
    def get_birth_location_side_effect(profile):
        if profile.id == 1:
            return sample_location_1
        elif profile.id == 2:
            return sample_location_2
        return None
    
    mock_db_helper.get_birth_location.side_effect = get_birth_location_side_effect
    
    list_result = await handle_list_profiles(mock_db_helper)
    text = list_result[0].text
    
    # Should show updated name
    assert "Sarah Marie Johnson" in text
    assert "Sarah Johnson" not in text or "Sarah Marie Johnson" in text  # Updated name, not old one


# ============================================================================
# Tests for remove_location
# ============================================================================

@pytest.mark.asyncio
async def test_remove_location_success(mock_db_helper):
    """Test remove_location with valid non-birth location."""
    # Setup
    location_to_delete = Location(
        id=10,
        profile_id=1,
        label="Office",
        latitude=32.7800,
        longitude=-96.8000,
        timezone="America/Chicago",
        is_current_home=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.get_location_by_id.return_value = location_to_delete
    mock_db_helper.delete_location.return_value = True
    
    arguments = {"location_id": 10}
    
    # Execute
    result = await handle_remove_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "Office" in text
    assert "ID: 10" in text
    assert "32.78" in text or "32.8" in text
    assert "-96.8" in text
    
    # Verify database methods called correctly
    mock_db_helper.get_location_by_id.assert_called_once_with(10)
    mock_db_helper.delete_location.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_remove_location_birth_location_error(mock_db_helper, sample_profile_1):
    """Test remove_location with birth location (should fail)."""
    # Setup
    birth_location = Location(
        id=1,
        profile_id=1,
        label="Birth",
        latitude=32.9483,
        longitude=-96.7297,
        timezone="America/Chicago",
        is_current_home=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.get_location_by_id.return_value = birth_location
    mock_db_helper.delete_location.side_effect = ValueError(
        f"Cannot delete location - it is the birth location for profile '{sample_profile_1.name}' (ID: {sample_profile_1.id})"
    )
    
    arguments = {"location_id": 1}
    
    # Execute
    result = await handle_remove_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "birth location" in text.lower()
    assert "Todd Waits" in text
    assert "cannot be removed" in text.lower()
    
    # Verify database methods called
    mock_db_helper.get_location_by_id.assert_called_once_with(1)
    mock_db_helper.delete_location.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_remove_location_not_found(mock_db_helper):
    """Test remove_location when location doesn't exist."""
    # Setup
    mock_db_helper.get_location_by_id.return_value = None
    
    arguments = {"location_id": 999}
    
    # Execute
    result = await handle_remove_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "999" in text
    assert "not found" in text.lower()
    
    # Should check location but NOT call delete
    mock_db_helper.get_location_by_id.assert_called_once_with(999)
    mock_db_helper.delete_location.assert_not_called()


@pytest.mark.asyncio
async def test_remove_location_missing_parameter(mock_db_helper):
    """Test remove_location with missing location_id."""
    arguments = {}
    
    # Execute
    result = await handle_remove_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error" in text
    assert "location_id is required" in text
    
    # Should NOT call database
    mock_db_helper.get_location_by_id.assert_not_called()
    mock_db_helper.delete_location.assert_not_called()


@pytest.mark.asyncio
async def test_remove_location_error_handling(mock_db_helper):
    """Test remove_location handles unexpected errors gracefully."""
    # Setup
    location = Location(
        id=10,
        profile_id=1,
        label="Office",
        latitude=32.7800,
        longitude=-96.8000,
        timezone="America/Chicago",
        is_current_home=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.get_location_by_id.return_value = location
    mock_db_helper.delete_location.side_effect = Exception("Database connection lost")
    
    arguments = {"location_id": 10}
    
    # Execute
    result = await handle_remove_location(mock_db_helper, arguments)
    
    # Assert
    assert len(result) == 1
    text = result[0].text
    
    assert "Error removing location" in text
    assert "Database connection lost" in text


@pytest.mark.asyncio
async def test_workflow_add_then_remove_location(mock_db_helper, sample_profile_1):
    """Test workflow: add location, then remove it."""
    # Step 1: Add location
    mock_db_helper.get_profile_by_id.return_value = sample_profile_1
    
    new_location = Location(
        id=15,
        profile_id=1,
        label="Temporary Office",
        latitude=32.7800,
        longitude=-96.8000,
        timezone="America/Chicago",
        is_current_home=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_db_helper.create_location.return_value = new_location
    
    add_args = {
        "profile_id": 1,
        "label": "Temporary Office",
        "latitude": 32.7800,
        "longitude": -96.8000,
        "timezone": "America/Chicago",
        "set_as_home": False
    }
    
    add_result = await handle_add_location(mock_db_helper, add_args)
    assert "Temporary Office" in add_result[0].text
    assert "ID: 15" in add_result[0].text
    
    # Step 2: Remove the location
    mock_db_helper.get_location_by_id.return_value = new_location
    mock_db_helper.delete_location.return_value = True
    
    remove_args = {"location_id": 15}
    
    remove_result = await handle_remove_location(mock_db_helper, remove_args)
    text = remove_result[0].text
    
    assert "✓" in text or "success" in text.lower()
    assert "Temporary Office" in text
    assert "Deleted" in text or "removed" in text.lower()
    
    # Verify both operations completed
    mock_db_helper.create_location.assert_called_once()
    mock_db_helper.delete_location.assert_called_once_with(15)
