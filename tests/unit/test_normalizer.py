"""
Unit Tests for Normalizer Service

These tests validate the normalizer's core logic in isolation, without
requiring a database connection. We use mocks and fixtures to simulate
external dependencies.

Test Organization:
- test_hash_generator: Tests for hash key generation
- test_normalize: Tests for job normalization logic
- test_normalize_edge_cases: Tests for error handling and edge cases
- test_normalize_enums: Tests for enum validation

Testing Concepts Used:
- Fixtures: Reusable test data
- Parametrize: Run same test with different inputs
- Assertions: Verify expected behavior
- Exception testing: Ensure errors are raised correctly
"""

import pytest
from datetime import datetime, timezone

from services.normalizer.hash_generator import (
    normalize_whitespace,
    generate_hash_key,
    validate_hash_key,
)
from services.normalizer.normalize import (
    normalize_job_posting,
    NormalizationError,
    VALID_REMOTE_TYPES,
    VALID_CONTRACT_TYPES,
    VALID_COMPANY_SIZES,
)


# ============================================================================
# Hash Generator Tests
# ============================================================================

class TestHashGenerator:
    """Tests for hash key generation functions"""

    def test_normalize_whitespace_basic(self):
        """Test basic whitespace normalization"""
        # Multiple spaces should become single space
        assert normalize_whitespace("Data   Engineer") == "Data Engineer"

        # Leading/trailing whitespace should be removed
        assert normalize_whitespace("  Data Engineer  ") == "Data Engineer"

        # Tabs and newlines should become spaces
        assert normalize_whitespace("Data\tEngineer\n") == "Data Engineer"

    def test_normalize_whitespace_edge_cases(self):
        """Test edge cases for whitespace normalization"""
        # Empty string
        assert normalize_whitespace("") == ""

        # None should return empty string
        assert normalize_whitespace(None) == ""

        # Only whitespace should return empty string
        assert normalize_whitespace("   \t\n   ") == ""

        # Already normalized string should remain unchanged
        assert normalize_whitespace("Data Engineer") == "Data Engineer"

    def test_generate_hash_key_basic(self):
        """Test basic hash key generation"""
        hash_key = generate_hash_key(
            "Acme Corp",
            "Data Engineer",
            "Montreal, QC"
        )

        # Hash should be 32 characters (MD5 hex)
        assert len(hash_key) == 32

        # Hash should be hexadecimal
        assert all(c in '0123456789abcdef' for c in hash_key)

    def test_generate_hash_key_deterministic(self):
        """Test that same inputs produce same hash"""
        hash1 = generate_hash_key("Acme Corp", "Data Engineer", "Montreal, QC")
        hash2 = generate_hash_key("Acme Corp", "Data Engineer", "Montreal, QC")

        assert hash1 == hash2

    def test_generate_hash_key_case_insensitive(self):
        """Test that hash is case-insensitive"""
        hash1 = generate_hash_key("ACME CORP", "Data Engineer", "Montreal, QC")
        hash2 = generate_hash_key("acme corp", "data engineer", "montreal, qc")

        # Different cases should produce same hash
        assert hash1 == hash2

    def test_generate_hash_key_whitespace_normalized(self):
        """Test that hash normalizes whitespace"""
        hash1 = generate_hash_key("Acme  Corp", "Data   Engineer", "Montreal,  QC")
        hash2 = generate_hash_key("Acme Corp", "Data Engineer", "Montreal, QC")

        # Different whitespace should produce same hash
        assert hash1 == hash2

    def test_generate_hash_key_different_inputs(self):
        """Test that different inputs produce different hashes"""
        hash1 = generate_hash_key("Acme Corp", "Data Engineer", "Montreal, QC")
        hash2 = generate_hash_key("Globex Inc", "Data Engineer", "Montreal, QC")
        hash3 = generate_hash_key("Acme Corp", "Software Engineer", "Montreal, QC")
        hash4 = generate_hash_key("Acme Corp", "Data Engineer", "Toronto, ON")

        # All hashes should be different
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash1 != hash4
        assert hash2 != hash3
        assert hash2 != hash4
        assert hash3 != hash4

    @pytest.mark.parametrize("company,title,location", [
        ("", "Data Engineer", "Montreal, QC"),
        ("Acme Corp", "", "Montreal, QC"),
        ("Acme Corp", "Data Engineer", ""),
        (None, "Data Engineer", "Montreal, QC"),
        ("Acme Corp", None, "Montreal, QC"),
        ("Acme Corp", "Data Engineer", None),
    ])
    def test_generate_hash_key_missing_fields(self, company, title, location):
        """Test that missing fields raise ValueError"""
        with pytest.raises(ValueError):
            generate_hash_key(company, title, location)

    def test_validate_hash_key_valid(self):
        """Test validation of valid hash keys"""
        # Generate a real hash
        valid_hash = generate_hash_key("Acme Corp", "Data Engineer", "Montreal, QC")
        assert validate_hash_key(valid_hash) is True

        # Test a manually created valid hash
        assert validate_hash_key("a1b2c3d4e5f6789012345678901234ab") is True

    @pytest.mark.parametrize("invalid_hash", [
        "too_short",                             # Too short
        "toolongbecauseithastoomanycharacters",  # Too long
        "g1b2c3d4e5f6789012345678901234ab",      # Invalid hex (contains 'g')
        "",                                      # Empty
        None,                                    # None
        12345,                                   # Not a string
    ])
    def test_validate_hash_key_invalid(self, invalid_hash):
        """Test validation of invalid hash keys"""
        assert validate_hash_key(invalid_hash) is False


# ============================================================================
# Normalize Job Posting Tests
# ============================================================================

class TestNormalizeJobPosting:
    """Tests for job posting normalization"""

    @pytest.fixture
    def valid_raw_job(self):
        """Fixture providing a valid raw job posting"""
        return {
            'provider_job_id': 'job_123',
            'job_link': 'https://example.com/job/123',
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'company_size': '51-200',
            'location': 'Montreal, QC, Canada',
            'remote_type': 'hybrid',
            'contract_type': 'full_time',
            'salary_min': 80000,
            'salary_max': 120000,
            'salary_currency': 'CAD',
            'description': 'We are seeking a Data Engineer...',
            'skills_raw': ['python', 'sql', 'airflow'],
            'posted_at': '2025-10-15T10:00:00Z',
            'apply_url': 'https://example.com/apply/123',
        }

    def test_normalize_valid_job(self, valid_raw_job):
        """Test normalization of a valid job posting"""
        normalized = normalize_job_posting(valid_raw_job, 'test_source')

        # Check that all required fields are present
        assert 'hash_key' in normalized
        assert len(normalized['hash_key']) == 32

        assert normalized['job_title'] == 'Data Engineer'
        assert normalized['company'] == 'Acme Corp'
        assert normalized['location'] == 'Montreal, QC, Canada'
        assert normalized['source'] == 'test_source'

        # Check optional fields
        assert normalized['provider_job_id'] == 'job_123'
        assert normalized['remote_type'] == 'hybrid'
        assert normalized['contract_type'] == 'full_time'
        assert normalized['company_size'] == '51-200'
        assert normalized['salary_min'] == 80000
        assert normalized['salary_max'] == 120000
        assert normalized['salary_currency'] == 'CAD'
        assert normalized['skills_raw'] == ['python', 'sql', 'airflow']

    def test_normalize_missing_optional_fields(self):
        """Test normalization with missing optional fields"""
        minimal_job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
        }

        normalized = normalize_job_posting(minimal_job, 'test_source')

        # Required fields should be present
        assert normalized['job_title'] == 'Data Engineer'
        assert normalized['company'] == 'Acme Corp'
        assert normalized['location'] == 'Montreal, QC'
        assert normalized['source'] == 'test_source'
        assert 'hash_key' in normalized

        # Optional fields should have defaults or None
        assert normalized['remote_type'] == 'unknown'
        assert normalized['contract_type'] == 'unknown'
        assert normalized['company_size'] == 'unknown'
        assert normalized['salary_min'] is None
        assert normalized['salary_max'] is None
        assert normalized['provider_job_id'] is None

    @pytest.mark.parametrize("missing_field", ['job_title', 'company', 'location'])
    def test_normalize_missing_required_fields(self, valid_raw_job, missing_field):
        """Test that missing required fields raise NormalizationError"""
        # Remove the required field
        del valid_raw_job[missing_field]

        with pytest.raises(NormalizationError):
            normalize_job_posting(valid_raw_job, 'test_source')

    @pytest.mark.parametrize("field,invalid_value", [
        ('job_title', ''),
        ('job_title', None),
        ('job_title', 123),
        ('company', ''),
        ('company', None),
        ('company', []),
        ('location', ''),
        ('location', None),
    ])
    def test_normalize_invalid_required_fields(self, valid_raw_job, field, invalid_value):
        """Test that invalid required fields raise NormalizationError"""
        valid_raw_job[field] = invalid_value

        with pytest.raises(NormalizationError):
            normalize_job_posting(valid_raw_job, 'test_source')

    def test_normalize_whitespace_in_fields(self):
        """Test that leading/trailing whitespace is stripped"""
        job = {
            'job_title': '  Data Engineer  ',
            'company': '  Acme Corp  ',
            'location': '  Montreal, QC  ',
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Whitespace should be stripped
        assert normalized['job_title'] == 'Data Engineer'
        assert normalized['company'] == 'Acme Corp'
        assert normalized['location'] == 'Montreal, QC'


# ============================================================================
# Enum Validation Tests
# ============================================================================

class TestEnumValidation:
    """Tests for enum field validation and defaults"""

    @pytest.mark.parametrize("remote_type", list(VALID_REMOTE_TYPES))
    def test_normalize_valid_remote_types(self, remote_type):
        """Test that all valid remote_type values are accepted"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'remote_type': remote_type,
        }

        normalized = normalize_job_posting(job, 'test_source')
        assert normalized['remote_type'] == remote_type

    @pytest.mark.parametrize("contract_type", list(VALID_CONTRACT_TYPES))
    def test_normalize_valid_contract_types(self, contract_type):
        """Test that all valid contract_type values are accepted"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'contract_type': contract_type,
        }

        normalized = normalize_job_posting(job, 'test_source')
        assert normalized['contract_type'] == contract_type

    @pytest.mark.parametrize("company_size", list(VALID_COMPANY_SIZES))
    def test_normalize_valid_company_sizes(self, company_size):
        """Test that all valid company_size values are accepted"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'company_size': company_size,
        }

        normalized = normalize_job_posting(job, 'test_source')
        assert normalized['company_size'] == company_size

    @pytest.mark.parametrize("invalid_value", [
        'invalid_type',
        'full-time',  # Wrong format (should be full_time)
        123,  # Not a string
    ])
    def test_normalize_invalid_remote_type(self, invalid_value):
        """Test that invalid remote_type falls back to 'unknown'"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'remote_type': invalid_value,
        }

        normalized = normalize_job_posting(job, 'test_source')
        # Invalid values should default to 'unknown'
        assert normalized['remote_type'] == 'unknown'

    def test_normalize_case_insensitive_enums(self):
        """Test that enum values are case-insensitive"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'remote_type': 'REMOTE',  # Uppercase
            'contract_type': 'Full_Time',  # Mixed case
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Should be normalized to lowercase
        assert normalized['remote_type'] == 'remote'
        assert normalized['contract_type'] == 'full_time'


# ============================================================================
# Salary Validation Tests
# ============================================================================

class TestSalaryNormalization:
    """Tests for salary field handling"""

    def test_normalize_valid_salary_range(self):
        """Test normalization of valid salary range"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'salary_min': 80000,
            'salary_max': 120000,
            'salary_currency': 'CAD',
        }

        normalized = normalize_job_posting(job, 'test_source')

        assert normalized['salary_min'] == 80000.0
        assert normalized['salary_max'] == 120000.0
        assert normalized['salary_currency'] == 'CAD'

    def test_normalize_swapped_salary_min_max(self):
        """Test that min > max is automatically fixed"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'salary_min': 120000,  # Swapped
            'salary_max': 80000,   # Swapped
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Should be automatically swapped
        assert normalized['salary_min'] == 80000.0
        assert normalized['salary_max'] == 120000.0

    @pytest.mark.parametrize("salary_str", ['80000', '120000.50'])
    def test_normalize_string_salaries(self, salary_str):
        """Test that string salary values are converted to float"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'salary_min': salary_str,
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Should be converted to float
        assert isinstance(normalized['salary_min'], float)
        assert normalized['salary_min'] == float(salary_str)

    def test_normalize_missing_salary(self):
        """Test that missing salary fields are None"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
        }

        normalized = normalize_job_posting(job, 'test_source')

        assert normalized['salary_min'] is None
        assert normalized['salary_max'] is None
        assert normalized['salary_currency'] is None


# ============================================================================
# Timestamp Parsing Tests
# ============================================================================

class TestTimestampParsing:
    """Tests for posted_at timestamp parsing"""

    def test_normalize_iso_timestamp(self):
        """Test parsing of ISO 8601 timestamp"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'posted_at': '2025-10-15T10:00:00Z',
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Should be parsed as datetime
        assert isinstance(normalized['posted_at'], datetime)
        assert normalized['posted_at'].year == 2025
        assert normalized['posted_at'].month == 10
        assert normalized['posted_at'].day == 15

    def test_normalize_unix_timestamp(self):
        """Test parsing of Unix timestamp"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'posted_at': 1729000000,  # Unix timestamp
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Should be parsed as datetime
        assert isinstance(normalized['posted_at'], datetime)

    def test_normalize_datetime_object(self):
        """Test that datetime objects are passed through"""
        dt = datetime(2025, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'posted_at': dt,
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Should remain datetime object
        assert normalized['posted_at'] == dt

    def test_normalize_invalid_timestamp(self):
        """Test that invalid timestamps become None"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
            'posted_at': 'invalid_date',
        }

        normalized = normalize_job_posting(job, 'test_source')

        # Invalid timestamp should be None
        assert normalized['posted_at'] is None

    def test_normalize_missing_timestamp(self):
        """Test that missing timestamp is None"""
        job = {
            'job_title': 'Data Engineer',
            'company': 'Acme Corp',
            'location': 'Montreal, QC',
        }

        normalized = normalize_job_posting(job, 'test_source')

        assert normalized['posted_at'] is None


# ============================================================================
# Data Flow Integration Tests
# ============================================================================

class TestDataFlowIntegration:
    """Tests for proper data flow from raw API response to normalized format"""

    def test_jsearch_raw_to_normalized_flow(self):
        """Test complete flow: raw JSearch API response → map_to_common → normalize"""
        from services.source_extractor.adapters.jsearch_adapter import JSearchAdapter
        from services.source_extractor.base import JobPostingRaw

        # Simulate raw JSearch API response (as stored in raw.job_postings_raw)
        raw_jsearch_payload = {
            'job_id': 'abc123',
            'job_title': 'Data Engineer',
            'employer_name': 'Acme Corp',
            'job_city': 'Montreal',
            'job_state': 'QC',
            'job_country': 'Canada',
            'job_is_remote': False,
            'job_employment_type': 'FULLTIME',
            'job_min_salary': 80000,
            'job_max_salary': 120000,
            'job_salary_currency': 'CAD',
            'job_description': 'We are hiring...',
            'job_apply_link': 'https://example.com/apply',
            'job_posted_at_datetime_utc': '2025-10-15T10:00:00Z',
        }

        # Map raw API response to common format (what adapter does)
        adapter = JSearchAdapter()
        job_raw = JobPostingRaw(source='jsearch', payload=raw_jsearch_payload)
        common_format = adapter.map_to_common(job_raw)

        # Verify common format has expected structure
        assert 'job_title' in common_format
        assert 'company' in common_format
        assert 'location' in common_format
        assert common_format['job_title'] == 'Data Engineer'
        assert common_format['company'] == 'Acme Corp'
        assert common_format['location'] == 'Montreal, QC, Canada'

        # Normalize the common format (what normalizer does)
        normalized = normalize_job_posting(common_format, 'jsearch')

        # Verify normalized format
        assert 'hash_key' in normalized
        assert len(normalized['hash_key']) == 32
        assert normalized['job_title'] == 'Data Engineer'
        assert normalized['company'] == 'Acme Corp'
        assert normalized['location'] == 'Montreal, QC, Canada'
        assert normalized['remote_type'] == 'onsite'
        assert normalized['contract_type'] == 'full_time'
        assert normalized['source'] == 'jsearch'

    def test_raw_payload_without_mapping_fails(self):
        """Test that normalizing raw API response directly fails (as expected)"""
        # Raw JSearch API response (NOT mapped to common format)
        raw_jsearch_payload = {
            'job_id': 'abc123',
            'job_title': 'Data Engineer',  # JSearch field name
            'employer_name': 'Acme Corp',  # Wrong - should be 'company'
            'job_city': 'Montreal',        # Wrong - should be part of 'location'
        }

        # This should fail because fields don't match expected common format
        with pytest.raises(NormalizationError):
            # Missing required 'company' and 'location' fields
            normalize_job_posting(raw_jsearch_payload, 'jsearch')


# ============================================================================
# Mark all tests as unit tests
# ============================================================================

pytestmark = pytest.mark.unit

