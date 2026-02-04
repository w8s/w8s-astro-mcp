"""Tests for swetest integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from w8s_astro_mcp.swetest_integration import SweetestIntegration, SweetestError
from w8s_astro_mcp.config import Config


# Sample swetest output for testing
SAMPLE_OUTPUT = """
date (dmy) 3.2.2026 greg.   12:00:00 UT
geo. long -96.729700, lat 32.948300, alt 0.000000
Houses system P (Placidus) for long= -96°43'47", lat=  32°56'54"
Sun             14 aq 39'38"    1° 0'50"
Moon             4 vi 54'57"   13°34'41"
Mercury         23 aq 54' 3"    1°46'23"
Venus           21 aq 18'49"    1°15'15"
Mars             8 aq 41' 8"    0°47' 1"
Jupiter         17 cn  5'18"   -0° 6'22"
Saturn          28 pi 53'24"    0° 6' 3"
Uranus          27 ta 27'36"   -0° 0' 2"
Neptune          0 ar 12'36"    0° 1'43"
Pluto            3 aq 46'34"    0° 1'54"
house  1        15 sc 30'12"  360°30'12"
house  2        12 sa 15'45"  330°15'45"
house  3        10 cp  8'22"  310° 8'22"
house  4        10 aq 12'18"  310°12'18"
house  5        12 pi 20'30"  330°20'30"
house  6        15 ar  2' 8"  345° 2' 8"
house  7        15 ta 30'12"  360°30'12"
house  8        12 ge 15'45"  330°15'45"
house  9        10 cn  8'22"  310° 8'22"
house 10        10 le 12'18"  310°12'18"
house 11        12 vi 20'30"  330°20'30"
house 12        15 li  2' 8"  345° 2' 8"
Ascendant       15 sc 30'12"  360°30'12"
MC              10 le 12'18"  310°12'18"
"""


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config with location data."""
    config_file = tmp_path / "config.json"
    config = Config(str(config_file))
    config.load()
    
    # Set up home location
    config.set_location(
        "home",
        32.9483,
        -96.7297,
        "America/Chicago",
        "Richardson, TX"
    )
    config.set_current_location("home")
    
    return config


class TestSweetestIntegration:
    """Test swetest integration."""
    
    @patch('subprocess.run')
    def test_verify_swetest_success(self, mock_run, mock_config):
        """Test that swetest verification succeeds."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        integration = SweetestIntegration(mock_config)
        assert integration.swetest_path == "swetest"
    
    @patch('subprocess.run')
    def test_verify_swetest_not_found(self, mock_run, mock_config):
        """Test error when swetest binary not found."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(SweetestError, match="not found"):
            SweetestIntegration(mock_config)
    
    @patch('subprocess.run')
    def test_get_current_transits_success(self, mock_run, mock_config):
        """Test getting transits successfully."""
        # Mock verification
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        integration = SweetestIntegration(mock_config)
        
        # Mock actual swetest call
        mock_run.return_value = Mock(
            returncode=0,
            stdout=SAMPLE_OUTPUT,
            stderr=""
        )
        
        result = integration.get_current_transits(
            date_str="2026-02-03",
            time_str="12:00"
        )
        
        # Verify parsed data
        assert "planets" in result
        assert "houses" in result
        assert "Sun" in result["planets"]
        assert result["planets"]["Sun"]["sign"] == "Aquarius"
        assert 1 in result["houses"]
    
    @patch('subprocess.run')
    def test_get_current_transits_default_date(self, mock_run, mock_config):
        """Test that default date is today."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        integration = SweetestIntegration(mock_config)
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=SAMPLE_OUTPUT,
            stderr=""
        )
        
        # Should use today's date by default
        result = integration.get_current_transits()
        
        assert "planets" in result
        
        # Verify swetest was called with today's date
        call_args = mock_run.call_args[0][0]
        today = datetime.now()
        expected_date = f"{today.day}.{today.month}.{today.year}"
        assert any(expected_date in arg for arg in call_args)
    
    @patch('subprocess.run')
    def test_get_current_transits_invalid_date(self, mock_run, mock_config):
        """Test that invalid date format raises error."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        integration = SweetestIntegration(mock_config)
        
        with pytest.raises(SweetestError, match="Invalid date format"):
            integration.get_current_transits(date_str="02/03/2026")
    
    @patch('subprocess.run')
    def test_get_current_transits_location_not_found(self, mock_run, mock_config):
        """Test error when location not found."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        integration = SweetestIntegration(mock_config)
        
        with pytest.raises(SweetestError, match="not found"):
            integration.get_current_transits(location_name="nonexistent")
    
    @patch('subprocess.run')
    def test_get_current_transits_swetest_fails(self, mock_run, mock_config):
        """Test error when swetest command fails."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        integration = SweetestIntegration(mock_config)
        
        # Simulate swetest failure
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: invalid parameters"
        )
        
        with pytest.raises(SweetestError, match="swetest failed"):
            integration.get_current_transits()
    
    @patch('subprocess.run')
    def test_uses_configured_house_system(self, mock_run, mock_config):
        """Test that configured house system is used."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        integration = SweetestIntegration(mock_config)
        
        # Change house system to Koch
        mock_config.set_house_system("K")
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=SAMPLE_OUTPUT,
            stderr=""
        )
        
        integration.get_current_transits()
        
        # Verify swetest was called with Koch house system
        call_args = mock_run.call_args[0][0]
        # Should have -house long,lat,K
        assert any("K" in arg and "-house" in arg for arg in call_args)
