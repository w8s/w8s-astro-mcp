"""Tests for handle_find_house_placements — natal, transit, connection, and error paths.

The handler is extracted into server.handle_find_house_placements() so we can
call it directly without piercing the MCP dispatcher decorator.
"""

import pytest
from unittest.mock import MagicMock, patch

from w8s_astro_mcp.server import handle_find_house_placements


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SAMPLE_HOUSES = {
    "1": {"degree": 20.61, "sign": "Cancer"},
    "2": {"degree": 11.91, "sign": "Leo"},
    "3": {"degree": 6.44, "sign": "Virgo"},
    "4": {"degree": 6.58, "sign": "Libra"},
    "5": {"degree": 12.21, "sign": "Scorpio"},
    "6": {"degree": 18.50, "sign": "Sagittarius"},
    "7": {"degree": 20.61, "sign": "Capricorn"},
    "8": {"degree": 11.91, "sign": "Aquarius"},
    "9": {"degree": 6.44, "sign": "Pisces"},
    "10": {"degree": 6.58, "sign": "Aries"},
    "11": {"degree": 12.21, "sign": "Taurus"},
    "12": {"degree": 18.50, "sign": "Gemini"},
}

SAMPLE_PLANETS = {
    "Sun": {"degree": 15.81, "sign": "Gemini", "is_retrograde": False},
    "Moon": {"degree": 23.42, "sign": "Aquarius", "is_retrograde": False},
    "Mercury": {"degree": 7.89, "sign": "Cancer", "is_retrograde": False},
    "Venus": {"degree": 21.87, "sign": "Cancer", "is_retrograde": False},
    "Mars": {"degree": 13.82, "sign": "Taurus", "is_retrograde": False},
    "Jupiter": {"degree": 25.12, "sign": "Cancer", "is_retrograde": False},
    "Saturn": {"degree": 12.69, "sign": "Aries", "is_retrograde": False},
    "Uranus": {"degree": 2.38, "sign": "Gemini", "is_retrograde": False},
    "Neptune": {"degree": 4.16, "sign": "Aries", "is_retrograde": False},
    "Pluto": {"degree": 5.30, "sign": "Aquarius", "is_retrograde": True},
}

NATAL_CHART = {
    "planets": SAMPLE_PLANETS,
    "houses": SAMPLE_HOUSES,
    "points": {"Ascendant": {"degree": 20.61, "sign": "Cancer"}},
    "metadata": {"date": "1981-05-06", "time": "00:50:00"},
}

TRANSIT_CHART = {
    "planets": SAMPLE_PLANETS,
    "houses": SAMPLE_HOUSES,
    "points": {},
    "metadata": {"date": "2026-06-06", "time": "12:00:00"},
}


def _mock_connection_house(number, degree, minutes, sign):
    h = MagicMock()
    h.house_number = number
    h.degree = degree
    h.minutes = minutes
    h.sign = sign
    return h


CONNECTION_HOUSES = [
    _mock_connection_house(1, 17, 47, "Virgo"),
    _mock_connection_house(2, 13, 10, "Libra"),
    _mock_connection_house(3, 12, 18, "Scorpio"),
    _mock_connection_house(4, 15, 8,  "Sagittarius"),
    _mock_connection_house(5, 19, 9,  "Capricorn"),
    _mock_connection_house(6, 20, 43, "Aquarius"),
    _mock_connection_house(7, 17, 47, "Pisces"),
    _mock_connection_house(8, 13, 10, "Aries"),
    _mock_connection_house(9, 12, 18, "Taurus"),
    _mock_connection_house(10, 15, 8, "Gemini"),
    _mock_connection_house(11, 19, 9, "Cancer"),
    _mock_connection_house(12, 20, 43, "Leo"),
]


# ---------------------------------------------------------------------------
# Natal path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_natal_default_owner():
    """date=natal with no profile_id uses owner profile."""
    import w8s_astro_mcp.server as srv
    with patch.object(srv, "get_natal_chart_data", return_value=NATAL_CHART) as m, \
         patch.object(srv, "init_db"):
        result = await handle_find_house_placements({"date": "natal"})

    assert "House Placements" in result[0].text
    m.assert_called_once_with(profile_id=None)


@pytest.mark.asyncio
async def test_natal_explicit_profile():
    """date=natal with profile_id passes that id to get_natal_chart_data."""
    import w8s_astro_mcp.server as srv
    with patch.object(srv, "get_natal_chart_data", return_value=NATAL_CHART) as m, \
         patch.object(srv, "init_db"):
        result = await handle_find_house_placements({"date": "natal", "profile_id": 3})

    assert "House Placements" in result[0].text
    m.assert_called_once_with(profile_id=3)


# ---------------------------------------------------------------------------
# Transit path — today's planets against profile natal houses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_today_uses_natal_houses():
    """date=today places transit planets against the profile's natal house system."""
    import w8s_astro_mcp.server as srv
    with patch.object(srv, "get_chart_for_date", return_value=TRANSIT_CHART) as mt, \
         patch.object(srv, "get_natal_chart_data", return_value=NATAL_CHART) as mn, \
         patch.object(srv, "init_db"):
        result = await handle_find_house_placements({"date": "today", "profile_id": 1})

    assert "House Placements" in result[0].text
    mt.assert_called_once()
    mn.assert_called_once_with(profile_id=1)


@pytest.mark.asyncio
async def test_today_no_profile_uses_owner():
    """date=today with no profile_id defaults to owner natal houses."""
    import w8s_astro_mcp.server as srv
    with patch.object(srv, "get_chart_for_date", return_value=TRANSIT_CHART), \
         patch.object(srv, "get_natal_chart_data", return_value=NATAL_CHART) as mn, \
         patch.object(srv, "init_db"):
        result = await handle_find_house_placements({"date": "today"})

    assert "House Placements" in result[0].text
    mn.assert_called_once_with(profile_id=None)


@pytest.mark.asyncio
async def test_specific_date_uses_natal_houses():
    """Specific date places transit planets against natal houses."""
    import w8s_astro_mcp.server as srv
    with patch.object(srv, "get_chart_for_date", return_value=TRANSIT_CHART) as mt, \
         patch.object(srv, "get_natal_chart_data", return_value=NATAL_CHART), \
         patch.object(srv, "init_db"):
        result = await handle_find_house_placements({"date": "2026-06-14", "profile_id": 1})

    assert "House Placements" in result[0].text
    mt.assert_called_once_with("2026-06-14", "12:00")


# ---------------------------------------------------------------------------
# Connection chart path
# ---------------------------------------------------------------------------

def _mock_db_for_connection(label="Todd & Liz @ The Ow8sis"):
    mock_db = MagicMock()
    mock_connection = MagicMock()
    mock_connection.label = label
    mock_db.get_connection_by_id.return_value = mock_connection
    mock_cached = MagicMock()
    mock_cached.is_valid = True
    mock_cached.id = 99
    mock_db.get_connection_chart.return_value = mock_cached
    mock_db.get_connection_houses.return_value = CONNECTION_HOUSES
    return mock_db


@pytest.mark.asyncio
async def test_connection_composite():
    """connection_id + chart_type=composite uses composite house cusps."""
    import w8s_astro_mcp.server as srv
    mock_db = _mock_db_for_connection()
    with patch.object(srv, "init_db", return_value=mock_db), \
         patch.object(srv, "get_chart_for_date", return_value=TRANSIT_CHART):
        result = await handle_find_house_placements({
            "date": "today",
            "connection_id": 3,
            "chart_type": "composite",
        })

    assert "Composite" in result[0].text
    assert "Todd & Liz" in result[0].text
    mock_db.get_connection_chart.assert_called_once_with(3, "composite")


@pytest.mark.asyncio
async def test_connection_davison():
    """connection_id + chart_type=davison uses Davison house cusps."""
    import w8s_astro_mcp.server as srv
    mock_db = _mock_db_for_connection()
    with patch.object(srv, "init_db", return_value=mock_db), \
         patch.object(srv, "get_chart_for_date", return_value=TRANSIT_CHART):
        result = await handle_find_house_placements({
            "date": "today",
            "connection_id": 3,
            "chart_type": "davison",
        })

    assert "Davison" in result[0].text
    mock_db.get_connection_chart.assert_called_once_with(3, "davison")


@pytest.mark.asyncio
async def test_connection_label_in_header():
    """Connection label appears in the report header."""
    import w8s_astro_mcp.server as srv
    mock_db = _mock_db_for_connection("My Special Connection")
    with patch.object(srv, "init_db", return_value=mock_db), \
         patch.object(srv, "get_chart_for_date", return_value=TRANSIT_CHART):
        result = await handle_find_house_placements({
            "date": "today",
            "connection_id": 3,
            "chart_type": "composite",
        })

    assert "My Special Connection" in result[0].text


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mutually_exclusive_error():
    """Both connection_id and profile_id returns a clear error."""
    import w8s_astro_mcp.server as srv
    with patch.object(srv, "init_db"):
        result = await handle_find_house_placements({
            "date": "today",
            "profile_id": 1,
            "connection_id": 3,
            "chart_type": "composite",
        })

    assert "mutually exclusive" in result[0].text.lower()


@pytest.mark.asyncio
async def test_missing_chart_type_error():
    """connection_id without chart_type returns a clear error."""
    import w8s_astro_mcp.server as srv
    with patch.object(srv, "init_db"):
        result = await handle_find_house_placements({
            "date": "today",
            "connection_id": 3,
        })

    assert "chart_type" in result[0].text


@pytest.mark.asyncio
async def test_connection_not_found():
    """Unknown connection_id returns a clear error."""
    import w8s_astro_mcp.server as srv
    mock_db = MagicMock()
    mock_db.get_connection_by_id.return_value = None
    with patch.object(srv, "init_db", return_value=mock_db):
        result = await handle_find_house_placements({
            "date": "today",
            "connection_id": 999,
            "chart_type": "composite",
        })

    assert "not found" in result[0].text.lower()


@pytest.mark.asyncio
async def test_connection_no_cached_chart():
    """Missing cached chart returns a helpful error."""
    import w8s_astro_mcp.server as srv
    mock_db = MagicMock()
    mock_db.get_connection_by_id.return_value = MagicMock(label="Test")
    mock_db.get_connection_chart.return_value = None
    with patch.object(srv, "init_db", return_value=mock_db):
        result = await handle_find_house_placements({
            "date": "today",
            "connection_id": 3,
            "chart_type": "composite",
        })

    assert "get_connection_chart" in result[0].text


@pytest.mark.asyncio
async def test_natal_date_with_connection_rejected():
    """date=natal with connection_id is rejected as ambiguous."""
    import w8s_astro_mcp.server as srv
    mock_db = _mock_db_for_connection()
    with patch.object(srv, "init_db", return_value=mock_db):
        result = await handle_find_house_placements({
            "date": "natal",
            "connection_id": 3,
            "chart_type": "composite",
        })

    assert "ambiguous" in result[0].text.lower()
