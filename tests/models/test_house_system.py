"""Comprehensive tests for HouseSystem model.

Test coverage:
- CREATE: Valid data, duplicates, invalid data, constraints
- READ: By ID, by code, filtering, not found
- UPDATE: Modify fields, constraint violations
- DELETE: Simple delete, cascade behavior
- CONSTRAINTS: Unique code, nullable fields, string lengths
- EDGE CASES: Empty strings, special characters, SQL injection attempts
"""

import pytest
from sqlalchemy.exc import IntegrityError

from w8s_astro_mcp.models import HouseSystem


# =============================================================================
# CREATE TESTS
# =============================================================================

class TestHouseSystemCreate:
    """Test creating HouseSystem records."""
    
    def test_create_valid_house_system(self, test_session):
        """Should create house system with valid data."""
        hs = HouseSystem(
            code="T",
            name="Test System",
            description="A test house system",
            is_default=False
        )
        test_session.add(hs)
        test_session.commit()
        
        assert hs.id is not None
        assert hs.code == "T"
        assert hs.name == "Test System"
        assert hs.description == "A test house system"
        assert hs.is_default is False
    
    def test_create_duplicate_code_fails(self, test_session, seeded_house_systems):
        """Should fail when creating duplicate code (unique constraint)."""
        duplicate = HouseSystem(
            code="P",  # Placidus already exists
            name="Duplicate Placidus",
            description="Should fail",
            is_default=False
        )
        test_session.add(duplicate)
        
        with pytest.raises(IntegrityError) as exc_info:
            test_session.commit()
        
        assert "unique" in str(exc_info.value).lower() or "code" in str(exc_info.value).lower()
    
    def test_create_without_code_fails(self, test_session):
        """Should fail when code is missing (NOT NULL constraint)."""
        hs = HouseSystem(
            name="No Code System",
            description="Missing code field"
        )
        test_session.add(hs)
        
        with pytest.raises(IntegrityError):
            test_session.commit()
    
    def test_create_without_name_fails(self, test_session):
        """Should fail when name is missing (NOT NULL constraint)."""
        hs = HouseSystem(
            code="X",
            description="Missing name field"
        )
        test_session.add(hs)
        
        with pytest.raises(IntegrityError):
            test_session.commit()
    
    def test_create_without_description_fails(self, test_session):
        """Should fail when description is missing (NOT NULL constraint)."""
        hs = HouseSystem(
            code="X",
            name="No Description"
        )
        test_session.add(hs)
        
        with pytest.raises(IntegrityError):
            test_session.commit()


# =============================================================================
# READ TESTS
# =============================================================================

class TestHouseSystemRead:
    """Test reading/querying HouseSystem records."""
    
    def test_read_by_id(self, test_session, seeded_house_systems):
        """Should retrieve house system by ID."""
        placidus = seeded_house_systems[0]  # First one is Placidus
        
        retrieved = test_session.query(HouseSystem).filter_by(id=placidus.id).first()
        
        assert retrieved is not None
        assert retrieved.id == placidus.id
        assert retrieved.code == "P"
    
    def test_read_by_code(self, test_session, seeded_house_systems):
        """Should retrieve house system by unique code."""
        whole_sign = test_session.query(HouseSystem).filter_by(code="W").first()
        
        assert whole_sign is not None
        assert whole_sign.name == "Whole Sign"
    
    def test_read_default_system(self, test_session, seeded_house_systems):
        """Should find the default house system."""
        default = test_session.query(HouseSystem).filter_by(is_default=True).first()
        
        assert default is not None
        assert default.code == "P"  # Placidus is default
        assert default.is_default is True
    
    def test_read_all_systems(self, test_session, seeded_house_systems):
        """Should retrieve all house systems."""
        all_systems = test_session.query(HouseSystem).all()
        
        assert len(all_systems) == 7  # We seeded 7 systems
    
    def test_read_nonexistent_id(self, test_session):
        """Should return None for nonexistent ID."""
        result = test_session.query(HouseSystem).filter_by(id=99999).first()
        
        assert result is None
    
    def test_read_nonexistent_code(self, test_session, seeded_house_systems):
        """Should return None for nonexistent code."""
        result = test_session.query(HouseSystem).filter_by(code="Z").first()
        
        assert result is None


# =============================================================================
# UPDATE TESTS
# =============================================================================

class TestHouseSystemUpdate:
    """Test updating HouseSystem records."""
    
    def test_update_description(self, test_session, seeded_house_systems):
        """Should update description field."""
        placidus = test_session.query(HouseSystem).filter_by(code="P").first()
        original_description = placidus.description
        
        placidus.description = "Updated description"
        test_session.commit()
        
        # Re-query to verify
        updated = test_session.query(HouseSystem).filter_by(code="P").first()
        assert updated.description == "Updated description"
        assert updated.description != original_description
    
    def test_update_is_default(self, test_session, seeded_house_systems):
        """Should update is_default flag."""
        whole_sign = test_session.query(HouseSystem).filter_by(code="W").first()
        assert whole_sign.is_default is False
        
        whole_sign.is_default = True
        test_session.commit()
        
        updated = test_session.query(HouseSystem).filter_by(code="W").first()
        assert updated.is_default is True
    
    def test_update_code_to_duplicate_fails(self, test_session, seeded_house_systems):
        """Should fail when updating code to existing value."""
        whole_sign = test_session.query(HouseSystem).filter_by(code="W").first()
        
        whole_sign.code = "P"  # Placidus already exists
        
        with pytest.raises(IntegrityError):
            test_session.commit()


# =============================================================================
# DELETE TESTS
# =============================================================================

class TestHouseSystemDelete:
    """Test deleting HouseSystem records."""
    
    def test_delete_house_system(self, test_session, seeded_house_systems):
        """Should delete house system."""
        initial_count = test_session.query(HouseSystem).count()
        
        koch = test_session.query(HouseSystem).filter_by(code="K").first()
        test_session.delete(koch)
        test_session.commit()
        
        final_count = test_session.query(HouseSystem).count()
        assert final_count == initial_count - 1
        
        # Verify it's gone
        deleted = test_session.query(HouseSystem).filter_by(code="K").first()
        assert deleted is None


# =============================================================================
# TO_DICT TESTS
# =============================================================================

class TestHouseSystemToDict:
    """Test to_dict() method."""
    
    def test_to_dict_contains_all_fields(self, test_session, seeded_house_systems):
        """Should include all fields in dictionary."""
        placidus = test_session.query(HouseSystem).filter_by(code="P").first()
        data = placidus.to_dict()
        
        assert "id" in data
        assert "code" in data
        assert "name" in data
        assert "description" in data
        assert "is_default" in data
    
    def test_to_dict_values_match(self, test_session, seeded_house_systems):
        """Should have correct values."""
        placidus = test_session.query(HouseSystem).filter_by(code="P").first()
        data = placidus.to_dict()
        
        assert data["code"] == "P"
        assert data["name"] == "Placidus"
        assert data["is_default"] is True


# =============================================================================
# EDGE CASE & SECURITY TESTS
# =============================================================================

class TestHouseSystemEdgeCases:
    """Test edge cases and security concerns."""
    
    def test_code_with_special_characters(self, test_session):
        """Should handle special characters in code (though not recommended)."""
        hs = HouseSystem(
            code="!",
            name="Special Code",
            description="Code with special character"
        )
        test_session.add(hs)
        test_session.commit()
        
        retrieved = test_session.query(HouseSystem).filter_by(code="!").first()
        assert retrieved.code == "!"
    
    def test_name_with_quotes(self, test_session):
        """Should handle quotes in name (SQL injection attempt)."""
        hs = HouseSystem(
            code="Q",
            name="System with 'quotes' and \"double quotes\"",
            description="Testing quote handling"
        )
        test_session.add(hs)
        test_session.commit()
        
        retrieved = test_session.query(HouseSystem).filter_by(code="Q").first()
        assert "quotes" in retrieved.name
    
    def test_description_with_sql_injection_attempt(self, test_session):
        """Should safely handle SQL injection attempts in description."""
        malicious_desc = "'; DROP TABLE house_systems; --"
        
        hs = HouseSystem(
            code="M",
            name="Malicious",
            description=malicious_desc
        )
        test_session.add(hs)
        test_session.commit()
        
        # Table should still exist
        count = test_session.query(HouseSystem).count()
        assert count > 0
        
        # Data should be stored as-is (parameterized queries prevent execution)
        retrieved = test_session.query(HouseSystem).filter_by(code="M").first()
        assert retrieved.description == malicious_desc
    
    def test_unicode_characters(self, test_session):
        """Should handle Unicode characters."""
        hs = HouseSystem(
            code="U",
            name="系統測試",  # Chinese characters
            description="Testing Unicode: émojis 🏠 and symbols ♈︎"
        )
        test_session.add(hs)
        test_session.commit()
        
        retrieved = test_session.query(HouseSystem).filter_by(code="U").first()
        assert retrieved.name == "系統測試"
        assert "🏠" in retrieved.description
    
    def test_very_long_description(self, test_session):
        """Should handle very long text fields."""
        long_desc = "A" * 10000  # 10k characters
        
        hs = HouseSystem(
            code="L",
            name="Long Description Test",
            description=long_desc
        )
        test_session.add(hs)
        test_session.commit()
        
        retrieved = test_session.query(HouseSystem).filter_by(code="L").first()
        assert len(retrieved.description) == 10000


# =============================================================================
# REPR TESTS
# =============================================================================

class TestHouseSystemRepr:
    """Test __repr__ method."""
    
    def test_repr_format(self, test_session, seeded_house_systems):
        """Should have readable repr."""
        placidus = test_session.query(HouseSystem).filter_by(code="P").first()
        repr_str = repr(placidus)
        
        assert "HouseSystem" in repr_str
        assert "code='P'" in repr_str
        assert "Placidus" in repr_str
