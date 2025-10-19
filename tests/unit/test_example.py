"""
Example unit tests demonstrating pytest patterns.

Unit tests focus on testing individual functions/classes in isolation.
They should be fast, independent, and not require external services.

To run these tests:
    pytest tests/unit/test_example.py -v
"""

import pytest


# Basic test example
@pytest.mark.unit
def test_basic_assertion():
    """Test basic assertions work correctly."""
    assert 1 + 1 == 2
    assert "hello".upper() == "HELLO"


# Test with fixture
@pytest.mark.unit
def test_sample_job_posting_fixture(sample_job_posting):
    """
    Test using a fixture from conftest.py.
    
    Fixtures are injected as function parameters.
    The sample_job_posting fixture provides test data.
    """
    assert sample_job_posting["job_title"] == "Data Engineer"
    assert sample_job_posting["company"] == "Acme Corp"
    assert "python" in sample_job_posting["skills_raw"]


# Test with parametrize (run same test with different inputs)
@pytest.mark.unit
@pytest.mark.parametrize(
    "input_string,expected_output",
    [
        ("data engineer", "Data Engineer"),
        ("senior data engineer", "Senior Data Engineer"),
        ("ANALYTICS ENGINEER", "Analytics Engineer"),
    ],
)
def test_title_case_transformation(input_string, expected_output):
    """
    Test title casing with multiple inputs.
    
    @pytest.mark.parametrize runs this test 3 times with different values.
    This is useful for testing edge cases without writing duplicate code.
    """
    assert input_string.title() == expected_output


# Test exception handling
@pytest.mark.unit
def test_division_by_zero():
    """
    Test that we can catch expected exceptions.
    
    Use pytest.raises() to verify code raises the correct exception.
    """
    with pytest.raises(ZeroDivisionError):
        _ = 1 / 0


# Example of testing a simple data transformation function
@pytest.mark.unit
def test_hash_key_generation():
    """
    Test hash key generation logic.
    
    In the real system, we'll use this to deduplicate jobs:
    hash_key = md5(company|title|location)
    """
    import hashlib
    
    company = "Acme Corp"
    title = "Data Engineer"
    location = "Montreal, QC"
    
    # Normalize and combine
    hash_input = f"{company.lower()}|{title.lower()}|{location.lower()}"
    hash_key = hashlib.md5(hash_input.encode()).hexdigest()
    
    # Verify it's a valid MD5 hash (32 hex characters)
    assert len(hash_key) == 32
    assert all(c in "0123456789abcdef" for c in hash_key)
    
    # Verify deterministic (same input = same output)
    hash_key_2 = hashlib.md5(hash_input.encode()).hexdigest()
    assert hash_key == hash_key_2


# Example of testing data validation
@pytest.mark.unit
@pytest.mark.parametrize(
    "remote_type,is_valid",
    [
        ("remote", True),
        ("hybrid", True),
        ("onsite", True),
        ("unknown", True),
        ("invalid_type", False),
        ("", False),
    ],
)
def test_remote_type_validation(remote_type, is_valid):
    """
    Test validation of remote_type enum values.
    
    This pattern is useful for testing data quality constraints.
    """
    valid_types = {"remote", "hybrid", "onsite", "unknown"}
    
    result = remote_type in valid_types and remote_type != ""
    assert result == is_valid


# Test using batch fixture
@pytest.mark.unit
def test_sample_job_batch_fixture(sample_job_batch):
    """Test batch processing with multiple job postings."""
    assert len(sample_job_batch) == 3
    assert all("job_title" in job for job in sample_job_batch)
    assert all("company" in job for job in sample_job_batch)
    
    # Test we can extract unique companies
    companies = {job["company"] for job in sample_job_batch}
    assert len(companies) == 3  # All different companies


# Example of a slow test (marked for optional skipping)
@pytest.mark.unit
@pytest.mark.slow
def test_slow_operation():
    """
    Example of a test marked as slow.
    
    Run with: pytest -m "not slow" to skip these
    """
    import time
    time.sleep(0.1)  # Simulate slow operation
    assert True


# Test that demonstrates mocking (when we have services to mock)
@pytest.mark.unit
def test_future_api_mock_placeholder():
    """
    Placeholder for future API mocking tests.
    
    When we implement the source-extractor service, we'll add tests like:
    - Mock API responses
    - Test error handling
    - Test rate limiting
    - Test pagination
    """
    # For now, just pass
    assert True  # Will be implemented in Phase 0.5

