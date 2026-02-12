"""Tests for profile management MCP tools."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from w8s_astro_mcp.tools.profile_management import (
    handle_list_profiles,
    handle_set_current_profile,
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
