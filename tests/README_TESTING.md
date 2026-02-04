# Testing Strategy

## Test Types

### 1. Unit Tests (Mocked)
**Files:** `test_swetest_parser.py`, `test_config.py`, `test_swetest_integration.py`

These tests use **mocking** to verify our code logic WITHOUT requiring swetest:
- ✅ Tests our Python code
- ✅ Fast (no external dependencies)
- ✅ Always run in CI/CD
- ❌ Don't verify swetest actually works

**Run:** `pytest tests/ -v`

### 2. Integration Tests (Real swetest)
**File:** `test_swetest_real.py`

These tests actually call the swetest binary:
- ✅ Verifies real swetest integration
- ✅ Catches platform-specific issues
- ❌ Requires swetest installed
- ❌ Skipped if swetest not available

**Run:** `pytest tests/test_swetest_real.py -v`

## Installing swetest

To run integration tests, install Swiss Ephemeris:

### macOS
```bash
brew install swisseph
```

### Linux
```bash
# Ubuntu/Debian
sudo apt-get install swisseph

# Or build from source:
# https://github.com/aloistr/swisseph
```

Then verify:
```bash
swetest -h
```

## Why Mock Tests?

**Mocked tests verify:**
- Date formatting logic
- Error handling
- Config → Integration → Parser flow
- Edge cases (invalid input, missing config)

**But they DON'T verify:**
- swetest binary actually works
- Platform-specific issues
- Real astronomical calculations

## Best Practice

1. **Development:** Run mocked tests (fast feedback)
2. **Before commit:** Run integration tests if swetest available
3. **CI/CD:** Run mocked tests always, integration tests if possible

## Current Status

```bash
# Mocked tests (always run)
pytest tests/ -k "not real" -v
# 33 tests passing

# Integration tests (requires swetest)
pytest tests/test_swetest_real.py -v
# 2 skipped (swetest not installed)
```
