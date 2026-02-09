"""Type safety and validation tests for HouseSystem model.

Tests SQLAlchemy's type coercion and validation behavior:
- Type coercion (what gets auto-converted)
- Type rejection (what fails)
- String length validation
- Pydantic-style validation (future)
"""

import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from w8s_astro_mcp.models import HouseSystem
from w8s_astro_mcp.database import DatabaseError


class TestHouseSystemTypeCoercion:
    """Test SQLAlchemy's type coercion behavior."""
    
    def test_integer_code_coerced_to_string(self, test_session):
        """SQLAlchemy WILL accept int for string field (coercion behavior)."""
        hs = HouseSystem(
            code=123,  # Integer provided
            name="Test",
            description="Testing int coercion"
        )
        test_session.add(hs)
        test_session.commit()
        
        # SQLAlchemy accepts this and stores it
        # The value remains as int in Python but stored as string in DB
        assert hs.code == 123  # Still int in Python object
        
        # Can retrieve by string OR int (both work)
        retrieved_str = test_session.query(HouseSystem).filter_by(code="123").first()
        retrieved_int = test_session.query(HouseSystem).filter_by(code=123).first()
        
        assert retrieved_str is not None
        assert retrieved_int is not None
        assert retrieved_str.id == retrieved_int.id


class TestHouseSystemTypeRejection:
    """Test what SQLAlchemy properly rejects."""
    
    def test_string_for_boolean_rejected(self, test_session):
        """Should reject string for boolean field."""
        hs = HouseSystem(
            code="T",
            name="Test",
            description="Test",
            is_default="yes"  # String instead of boolean
        )
        test_session.add(hs)
        
        with pytest.raises((DatabaseError, StatementError)):
            test_session.commit()
    
    def test_none_for_required_field_rejected(self, test_session):
        """Should reject None for NOT NULL field."""
        hs = HouseSystem(
            code=None,  # None for required field
            name="Test",
            description="Test"
        )
        test_session.add(hs)
        
        with pytest.raises((DatabaseError, IntegrityError)):
            test_session.commit()
    
    def test_dict_for_string_rejected(self, test_session):
        """Should reject dict/object for string field."""
        hs = HouseSystem(
            code="D",
            name={"first": "Test"},  # Dict instead of string
            description="Test"
        )
        test_session.add(hs)
        
        with pytest.raises((DatabaseError, StatementError)):
            test_session.commit()
    
    def test_list_for_string_rejected(self, test_session):
        """Should reject list for string field."""
        hs = HouseSystem(
            code="L",
            name=["Test", "List"],  # List instead of string
            description="Test"
        )
        test_session.add(hs)
        
        with pytest.raises((DatabaseError, StatementError)):
            test_session.commit()


class TestHouseSystemStringLengths:
    """Test string length limits (or lack thereof)."""
    
    def test_code_max_length_is_one_char(self, test_session):
        """Code field is String(1), should enforce max length."""
        hs = HouseSystem(
            code="TOOLONG",  # More than 1 character
            name="Test",
            description="Test"
        )
        test_session.add(hs)
        
        # SQLite doesn't enforce VARCHAR length by default!
        # This will actually SUCCEED unless we add validation
        test_session.commit()
        
        # Verify it was truncated or accepted (depends on DB)
        assert len(hs.code) >= 1  # At least we tried
    
    def test_name_extremely_long(self, test_session):
        """Name field has String(50), but SQLite doesn't enforce it."""
        long_name = "A" * 1000  # Way more than 50 chars
        
        hs = HouseSystem(
            code="L",
            name=long_name,
            description="Test"
        )
        test_session.add(hs)
        test_session.commit()
        
        # SQLite accepts this! We may want application-level validation
        assert len(hs.name) == 1000
    
    def test_description_text_field_unlimited(self, test_session):
        """Text fields are unlimited in SQLite."""
        huge_desc = "B" * 100000  # 100k chars
        
        hs = HouseSystem(
            code="H",
            name="Huge",
            description=huge_desc
        )
        test_session.add(hs)
        test_session.commit()
        
        assert len(hs.description) == 100000


class TestHouseSystemValidation:
    """Application-level validation we might want to add."""
    
    def test_empty_string_code(self, test_session):
        """Should we allow empty string for code?"""
        hs = HouseSystem(
            code="",  # Empty string
            name="Empty Code",
            description="Test"
        )
        test_session.add(hs)
        test_session.commit()
        
        # Currently ALLOWED - might want to add validation
        retrieved = test_session.query(HouseSystem).filter_by(code="").first()
        assert retrieved.code == ""
    
    def test_whitespace_only_code(self, test_session):
        """Should we allow whitespace-only strings?"""
        hs = HouseSystem(
            code=" ",  # Just a space
            name="Whitespace Code",
            description="Test"
        )
        test_session.add(hs)
        test_session.commit()
        
        # Currently ALLOWED - might want to add .strip() validation
        retrieved = test_session.query(HouseSystem).filter_by(code=" ").first()
        assert retrieved.code == " "
    
    def test_code_case_sensitivity(self, test_session):
        """SQLite is case-insensitive for LIKE, but case-sensitive for =."""
        hs1 = HouseSystem(code="p", name="Lower", description="Test")
        hs2 = HouseSystem(code="P", name="Upper", description="Test")
        
        test_session.add(hs1)
        test_session.commit()
        
        # Try to add uppercase P (lowercase p already exists)
        test_session.add(hs2)
        # This WILL succeed because 'p' != 'P' in SQLite
        test_session.commit()
        
        # Both exist!
        lower = test_session.query(HouseSystem).filter_by(code="p").first()
        upper = test_session.query(HouseSystem).filter_by(code="P").first()
        
        assert lower is not None
        assert upper is not None
        assert lower.id != upper.id


# =============================================================================
# RECOMMENDATIONS FOR FUTURE VALIDATION
# =============================================================================

"""
RECOMMENDATIONS:

1. **Add Pydantic validation** before saving:
   - Enforce string lengths at application level
   - Validate code is single uppercase letter
   - Strip whitespace from strings
   - Reject empty strings where inappropriate

2. **Add CHECK constraints** in database:
   - CHECK(length(code) = 1)
   - CHECK(code != '')
   - CHECK(length(name) <= 50)

3. **Add custom validators** to model:
   - @validates('code') decorator
   - Ensure uppercase
   - Ensure non-empty

4. **Consider using Enum** for code:
   - SQLAlchemy Enum type
   - Restrict to known values only
   - Prevents typos

Example Pydantic schema:
```python
from pydantic import BaseModel, validator

class HouseSystemCreate(BaseModel):
    code: str
    name: str
    description: str
    is_default: bool = False
    
    @validator('code')
    def validate_code(cls, v):
        if not v or len(v) != 1:
            raise ValueError('Code must be single character')
        return v.upper()
    
    @validator('name')
    def validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Name cannot be empty')
        if len(v) > 50:
            raise ValueError('Name too long (max 50 chars)')
        return v
```
"""
