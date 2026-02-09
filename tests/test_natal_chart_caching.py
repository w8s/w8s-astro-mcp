"""Unit tests for natal chart caching in config.

DESIGN DECISION (2026-02-09):
Natal chart data is cached in config.json to avoid repeated swetest calls.
This test file ensures the caching behavior works correctly.
"""

import pytest
from datetime import datetime
from w8s_astro_mcp.config import Config


class TestNatalChartCaching:
    """Test natal chart caching functionality."""
    
    def test_get_natal_chart_returns_none_by_default(self, tmp_path):
        """Test that natal chart is None before caching."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        assert config.get_natal_chart() is None
    
    def test_set_and_get_natal_chart(self, tmp_path):
        """Test caching and retrieving natal chart."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        # Sample natal chart data
        chart_data = {
            "planets": {
                "Sun": {"sign": "Taurus", "degree": 15.41},
                "Moon": {"sign": "Gemini", "degree": 11.86}
            },
            "houses": {
                "1": {"sign": "Scorpio", "degree": 11.75},
                "2": {"sign": "Sagittarius", "degree": 10.97}
            },
            "points": {
                "Ascendant": {"sign": "Scorpio", "degree": 11.75}
            },
            "metadata": {"date": "1981-05-06", "time": "00:50:00"}
        }
        
        config.set_natal_chart(chart_data)
        
        cached = config.get_natal_chart()
        assert cached is not None
        assert "planets" in cached
        assert "houses" in cached
        assert "points" in cached
        assert "metadata" in cached
        assert "cached_at" in cached  # Should add timestamp
        
        # Verify data integrity
        assert cached["planets"]["Sun"]["sign"] == "Taurus"
        assert cached["houses"]["1"]["sign"] == "Scorpio"
    
    def test_natal_chart_includes_timestamp(self, tmp_path):
        """Test that caching adds a timestamp."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        chart_data = {
            "planets": {},
            "houses": {},
            "points": {},
            "metadata": {}
        }
        
        config.set_natal_chart(chart_data)
        cached = config.get_natal_chart()
        
        assert "cached_at" in cached
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(cached["cached_at"])
    
    def test_natal_chart_persists_after_save(self, tmp_path):
        """Test that cached natal chart persists to disk."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        chart_data = {
            "planets": {"Sun": {"sign": "Taurus", "degree": 15.41}},
            "houses": {"1": {"sign": "Scorpio", "degree": 11.75}},
            "points": {},
            "metadata": {}
        }
        
        config.set_natal_chart(chart_data)
        config.save()
        
        # Load in new instance
        config2 = Config(str(config_file))
        config2.load()
        
        cached = config2.get_natal_chart()
        assert cached is not None
        assert cached["planets"]["Sun"]["sign"] == "Taurus"
    
    def test_clear_natal_chart_cache(self, tmp_path):
        """Test clearing the natal chart cache."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        chart_data = {
            "planets": {},
            "houses": {},
            "points": {},
            "metadata": {}
        }
        
        config.set_natal_chart(chart_data)
        assert config.get_natal_chart() is not None
        
        config.clear_natal_chart_cache()
        assert config.get_natal_chart() is None
    
    def test_set_birth_data_clears_natal_chart_cache(self, tmp_path):
        """Test that changing birth data clears the natal chart cache.
        
        This is critical - if birth data changes, the cached natal chart
        becomes invalid and must be recalculated.
        """
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        # Set initial birth data and cache chart
        location1 = {
            "name": "St. Louis, MO",
            "latitude": 38.637,
            "longitude": -90.263,
            "timezone": "America/Chicago"
        }
        config.set_birth_data("1981-05-06", "00:50", location1)
        
        chart_data = {
            "planets": {"Sun": {"sign": "Taurus", "degree": 15.41}},
            "houses": {"1": {"sign": "Scorpio", "degree": 11.75}},
            "points": {},
            "metadata": {}
        }
        config.set_natal_chart(chart_data)
        assert config.get_natal_chart() is not None
        
        # Change birth data - should clear cache
        location2 = {
            "name": "New York, NY",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York"
        }
        config.set_birth_data("1990-01-01", "12:00", location2)
        
        # Cache should be cleared
        assert config.get_natal_chart() is None
    
    def test_natal_chart_with_all_12_houses(self, tmp_path):
        """Test caching chart with all 12 houses.
        
        DESIGN DECISION (2026-02-09):
        House keys are strings ("1", "2", ..., "12"). This test ensures
        all 12 houses are cached correctly with string keys.
        """
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        chart_data = {
            "planets": {},
            "houses": {
                "1": {"sign": "Scorpio", "degree": 11.75},
                "2": {"sign": "Sagittarius", "degree": 10.97},
                "3": {"sign": "Capricorn", "degree": 13.16},
                "4": {"sign": "Aquarius", "degree": 17.12},
                "5": {"sign": "Pisces", "degree": 19.62},
                "6": {"sign": "Aries", "degree": 17.91},
                "7": {"sign": "Taurus", "degree": 11.75},
                "8": {"sign": "Gemini", "degree": 10.97},
                "9": {"sign": "Cancer", "degree": 13.16},
                "10": {"sign": "Leo", "degree": 17.12},
                "11": {"sign": "Virgo", "degree": 19.62},
                "12": {"sign": "Libra", "degree": 17.91}
            },
            "points": {},
            "metadata": {}
        }
        
        config.set_natal_chart(chart_data)
        cached = config.get_natal_chart()
        
        # Verify all 12 houses are present with string keys
        for house_num in range(1, 13):
            assert str(house_num) in cached["houses"], f"House {house_num} not cached"
    
    def test_natal_chart_with_ascendant_and_mc(self, tmp_path):
        """Test caching chart with Ascendant and MC points."""
        config_file = tmp_path / "config.json"
        config = Config(str(config_file))
        config.load()
        
        chart_data = {
            "planets": {},
            "houses": {},
            "points": {
                "Ascendant": {"sign": "Scorpio", "degree": 11.75},
                "MC": {"sign": "Leo", "degree": 17.12}
            },
            "metadata": {}
        }
        
        config.set_natal_chart(chart_data)
        cached = config.get_natal_chart()
        
        assert "Ascendant" in cached["points"]
        assert "MC" in cached["points"]
        assert cached["points"]["Ascendant"]["sign"] == "Scorpio"
        assert cached["points"]["MC"]["sign"] == "Leo"
