"""Unit tests for swetest parser."""

import pytest
from w8s_astro_mcp.parsers.swetest import parse_degree, parse_swetest_output


class TestParseDegree:
    """Test degree string parsing."""
    
    def test_parse_standard_format(self):
        """Test parsing standard format: '14 aq 39'38\"'"""
        result = parse_degree("14 aq 39'38\"")
        assert result is not None
        assert result["sign"] == "Aquarius"
        assert result["degree"] == pytest.approx(14.660555555555556)
        assert result["formatted"] == "14°39'38\""
    
    def test_parse_with_space_before_seconds(self):
        """Test parsing with space before seconds: '23 aq 54' 3\"'"""
        result = parse_degree("23 aq 54' 3\"")
        assert result is not None
        assert result["sign"] == "Aquarius"
        assert result["degree"] == pytest.approx(23.90083333333333)
        assert result["formatted"] == "23°54'3\""
    
    def test_parse_zero_degree(self):
        """Test parsing zero degree position."""
        result = parse_degree("0 ar 12'36\"")
        assert result is not None
        assert result["sign"] == "Aries"
        assert result["degree"] == pytest.approx(0.21)
    
    def test_parse_all_signs(self):
        """Test parsing all zodiac signs."""
        signs = {
            "ar": "Aries", "ta": "Taurus", "ge": "Gemini",
            "cn": "Cancer", "le": "Leo", "vi": "Virgo",
            "li": "Libra", "sc": "Scorpio", "sa": "Sagittarius",
            "cp": "Capricorn", "aq": "Aquarius", "pi": "Pisces"
        }
        for abbr, name in signs.items():
            result = parse_degree(f"15 {abbr} 30'0\"")
            assert result["sign"] == name
    
    def test_invalid_format(self):
        """Test that invalid formats return None."""
        assert parse_degree("invalid") is None
        assert parse_degree("") is None
        assert parse_degree("15 xx 30'0\"") is None  # Invalid sign


class TestParseSweetestOutput:
    """Test full swetest output parsing."""
    
    def test_parse_metadata(self):
        """Test parsing date, time, location, and house system."""
        output = """
date (dmy) 3.2.2026 greg.   12:00:00 UT
geo. long -74.006000, lat 40.713000, alt 0.000000
Houses system P (Placidus) for long= -74°00'22", lat=  40°42'47"
Sun             14 aq 39'38"    1° 0'50"
house  1        23 cp 22' 8"  403°44'50"
"""
        result = parse_swetest_output(output)
        
        assert result["metadata"]["date"] == "2026-02-03"
        assert result["metadata"]["time"] == "12:00:00"
        assert result["metadata"]["longitude"] == -74.006
        assert result["metadata"]["latitude"] == 40.713
        assert result["metadata"]["house_system"] == "Placidus"
    
    def test_parse_planets(self):
        """Test parsing planetary positions."""
        output = """
Sun             14 aq 39'38"    1° 0'50"
Moon             4 vi 54'57"   13°34'41"
Mercury         23 aq 54' 3"    1°46'23"
Mars             8 aq 41' 8"    0°47' 1"
house  1        23 cp 22' 8"  403°44'50"
"""
        result = parse_swetest_output(output)
        
        # Test Sun
        assert "Sun" in result["planets"]
        assert result["planets"]["Sun"]["sign"] == "Aquarius"
        assert result["planets"]["Sun"]["degree"] == pytest.approx(14.660555555555556)
        
        # Test Mercury (has space before seconds)
        assert "Mercury" in result["planets"]
        assert result["planets"]["Mercury"]["sign"] == "Aquarius"
        assert result["planets"]["Mercury"]["degree"] == pytest.approx(23.90083333333333)
        
        # Test all expected planets present
        assert "Moon" in result["planets"]
        assert "Mars" in result["planets"]
    
    def test_parse_houses(self):
        """Test parsing house cusps.
        
        DESIGN DECISION (2026-02-09):
        House numbers are stored as STRING keys ("1", "2", ..., "12") not integers.
        This was chosen because:
        1. JSON natively supports string keys better than integer keys
        2. Consistent with how the parser extracts them from swetest output
        3. Avoids type conversion issues between Python and JSON
        
        If this test fails in the future because houses have integer keys,
        THE CODE IS BROKEN, NOT THE TEST. Revert the code change.
        """
        output = """
Sun             14 aq 39'38"    1° 0'50"
house  1        23 cp 22' 8"  403°44'50"
house  2         6 pi 55'37"  489°46'17"
house 10        15 sc 56'55"  361°17'40"
"""
        result = parse_swetest_output(output)
        
        assert "1" in result["houses"]  # House keys are strings
        assert result["houses"]["1"]["sign"] == "Capricorn"
        assert result["houses"]["1"]["degree"] == pytest.approx(23.36888888888889)
        
        assert "2" in result["houses"]
        assert result["houses"]["2"]["sign"] == "Pisces"
        
        assert "10" in result["houses"]
        assert result["houses"]["10"]["sign"] == "Scorpio"
    
    def test_parse_special_points(self):
        """Test parsing Ascendant and MC."""
        output = """
Sun             14 aq 39'38"    1° 0'50"
house  1        23 cp 22' 8"  403°44'50"
Ascendant       23 cp 22' 8"  403°44'50"
MC              15 sc 56'55"  361°17'40"
"""
        result = parse_swetest_output(output)
        
        assert "Ascendant" in result["points"]
        assert result["points"]["Ascendant"]["sign"] == "Capricorn"
        
        assert "MC" in result["points"]
        assert result["points"]["MC"]["sign"] == "Scorpio"
    
    def test_parse_complete_output(self):
        """Test parsing complete swetest output with all elements.
        
        DESIGN DECISION (2026-02-09):
        House numbers are stored as STRING keys ("1", "2", ..., "12") not integers.
        See test_parse_houses() for full rationale.
        """
        # Use the actual test data from test_parser.py
        with open("tests/test_parser.py", "r") as f:
            content = f.read()
            # Extract test_output from the file
            start = content.find('test_output = """')
            end = content.find('"""', start + 20)
            test_output = content[start+18:end]
        
        result = parse_swetest_output(test_output)
        
        # Verify we got all 10 planets
        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars", 
                          "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        for planet in expected_planets:
            assert planet in result["planets"], f"{planet} not found in parsed output"
        
        # Verify we got all 12 houses (house keys are strings)
        for house_num in range(1, 13):
            assert str(house_num) in result["houses"], f"House {house_num} not found"
        
        # Verify special points
        assert "Ascendant" in result["points"]
        assert "MC" in result["points"]
        
        # Verify metadata
        assert "date" in result["metadata"]
        assert "house_system" in result["metadata"]
    
    def test_empty_output_raises_error(self):
        """Test that empty output raises SweetestParseError."""
        from w8s_astro_mcp.parsers.swetest import SweetestParseError
        
        with pytest.raises(SweetestParseError, match="empty"):
            parse_swetest_output("")
        
        with pytest.raises(SweetestParseError, match="empty"):
            parse_swetest_output("   ")
    
    def test_malformed_output_raises_error(self):
        """Test that output with no valid data raises SweetestParseError."""
        from w8s_astro_mcp.parsers.swetest import SweetestParseError
        
        output = """
This is not valid swetest output
Just random text
No planets or houses here
"""
        with pytest.raises(SweetestParseError, match="Missing planets or houses"):
            parse_swetest_output(output)
