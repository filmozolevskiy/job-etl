"""
Unit tests for JSearch API Adapter.

These tests use mocked API responses to verify adapter behavior
without making real API calls.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from services.source_extractor.adapters.jsearch_adapter import JSearchAdapter
from services.source_extractor.base import JobPostingRaw


# Sample JSearch API response for testing
SAMPLE_JSEARCH_RESPONSE = {
    "status": "OK",
    "request_id": "test-request-123",
    "parameters": {
        "query": "software engineer",
        "location": "United States",
        "page": 1,
        "num_pages": 1,
    },
    "data": [
        {
            "job_id": "test-job-1",
            "employer_name": "TechCorp Inc",
            "employer_logo": "https://example.com/logo.png",
            "employer_website": "https://techcorp.com",
            "job_publisher": "LinkedIn",
            "job_employment_type": "FULLTIME",
            "job_title": "Senior Software Engineer",
            "job_apply_link": "https://example.com/apply/123",
            "job_apply_is_direct": False,
            "job_apply_quality_score": 0.85,
            "job_description": "We are looking for a talented software engineer...",
            "job_is_remote": True,
            "job_posted_at_timestamp": 1704067200,
            "job_posted_at_datetime_utc": "2024-01-01T00:00:00.000Z",
            "job_city": "San Francisco",
            "job_state": "CA",
            "job_country": "US",
            "job_latitude": 37.7749,
            "job_longitude": -122.4194,
            "job_benefits": None,
            "job_min_salary": 120000,
            "job_max_salary": 180000,
            "job_salary_currency": "USD",
            "job_salary_period": "YEAR",
        },
        {
            "job_id": "test-job-2",
            "employer_name": "StartupXYZ",
            "employer_logo": None,
            "employer_website": None,
            "job_publisher": "Indeed",
            "job_employment_type": "CONTRACT",
            "job_title": "Backend Developer",
            "job_apply_link": "https://example.com/apply/456",
            "job_apply_is_direct": True,
            "job_apply_quality_score": 0.72,
            "job_description": "Contract position for backend development...",
            "job_is_remote": False,
            "job_posted_at_timestamp": 1704153600,
            "job_posted_at_datetime_utc": "2024-01-02T00:00:00.000Z",
            "job_city": "Austin",
            "job_state": "TX",
            "job_country": "US",
            "job_latitude": 30.2672,
            "job_longitude": -97.7431,
            "job_benefits": None,
            "job_min_salary": None,
            "job_max_salary": None,
            "job_salary_currency": None,
            "job_salary_period": None,
        },
    ],
}


class TestJSearchAdapterInit:
    """Test adapter initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key parameter."""
        adapter = JSearchAdapter(api_key="test-key", max_jobs=10)

        assert adapter.source_name == "jsearch"
        assert adapter.api_key == "test-key"
        assert adapter.max_jobs == 10
        assert adapter.api_call_count == 0

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization with environment variable."""
        monkeypatch.setenv("JSEARCH_API_KEY", "env-test-key")
        monkeypatch.setenv("JSEARCH_BASE_URL", "https://test.api.com")

        adapter = JSearchAdapter()

        assert adapter.api_key == "env-test-key"
        assert adapter.base_url == "https://test.api.com"

    def test_init_without_api_key_raises_error(self, monkeypatch):
        """Test initialization fails without API key."""
        monkeypatch.delenv("JSEARCH_API_KEY", raising=False)

        with pytest.raises(ValueError, match="JSEARCH_API_KEY must be set"):
            JSearchAdapter()

    def test_repr(self):
        """Test string representation."""
        adapter = JSearchAdapter(api_key="test-key", max_jobs=15)

        repr_str = repr(adapter)

        assert "JSearchAdapter" in repr_str
        assert "jsearch" in repr_str
        assert "max_jobs=15" in repr_str
        assert "api_calls=0" in repr_str


class TestJSearchAdapterFetch:
    """Test the fetch() method."""

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_success(self, mock_get):
        """Test successful job fetching."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_JSEARCH_RESPONSE
        mock_get.return_value = mock_response

        # Create adapter and fetch
        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)
        jobs, next_page = adapter.fetch()

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args

        assert "job-search" in call_args[0][0]
        assert call_args[1]["params"]["query"] == "software engineer"
        assert call_args[1]["params"]["page"] == 1
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"

        # Verify results
        assert len(jobs) == 2
        assert all(isinstance(job, JobPostingRaw) for job in jobs)
        assert jobs[0].source == "jsearch"
        assert jobs[0].provider_job_id == "test-job-1"
        assert jobs[1].provider_job_id == "test-job-2"

        # Verify pagination
        assert next_page == "2"  # Should have next page
        assert adapter.api_call_count == 1

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_with_page_token(self, mock_get):
        """Test fetching with pagination."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_JSEARCH_RESPONSE
        mock_get.return_value = mock_response

        # Create adapter and fetch page 3
        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)
        jobs, next_page = adapter.fetch(page_token="3")

        # Verify page parameter
        call_args = mock_get.call_args
        assert call_args[1]["params"]["page"] == 3

        # Verify next page
        assert next_page == "4"

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_stops_at_max_jobs(self, mock_get):
        """Test fetching stops when max_jobs reached."""
        # Setup mock response with 2 jobs
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_JSEARCH_RESPONSE
        mock_get.return_value = mock_response

        # Create adapter with max_jobs=2
        adapter = JSearchAdapter(api_key="test-key", max_jobs=2)
        jobs, next_page = adapter.fetch()

        # Should return 2 jobs but no next page (reached limit)
        assert len(jobs) == 2
        assert next_page is None  # No more pages

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_empty_response(self, mock_get):
        """Test handling of empty response."""
        # Setup mock response with no data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK", "data": []}
        mock_get.return_value = mock_response

        # Create adapter and fetch
        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)
        jobs, next_page = adapter.fetch()

        # Should return empty list and no next page
        assert jobs == []
        assert next_page is None

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_handles_401_error(self, mock_get):
        """Test handling of 401 Unauthorized error."""
        # Setup mock response with 401
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        mock_get.return_value = mock_response

        # Create adapter and fetch
        adapter = JSearchAdapter(api_key="invalid-key", max_jobs=20)

        # Should raise HTTPError
        with pytest.raises(requests.exceptions.RequestException):
            adapter.fetch()

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_handles_429_error(self, mock_get):
        """Test handling of 429 Rate Limit error."""
        # Setup mock response with 429
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_get.return_value = mock_response

        # Create adapter and fetch
        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)

        # Should raise HTTPError
        with pytest.raises(requests.exceptions.RequestException):
            adapter.fetch()

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_tracks_api_calls(self, mock_get):
        """Test that API calls are tracked correctly."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_JSEARCH_RESPONSE
        mock_get.return_value = mock_response

        # Create adapter and make multiple fetches
        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)

        adapter.fetch()
        assert adapter.api_call_count == 1

        adapter.fetch(page_token="2")
        assert adapter.api_call_count == 2

        adapter.fetch(page_token="3")
        assert adapter.api_call_count == 3


class TestJSearchAdapterMapping:
    """Test the map_to_common() method."""

    def test_map_to_common_full_data(self):
        """Test mapping with complete job data."""
        adapter = JSearchAdapter(api_key="test-key")

        # Create JobPostingRaw with full data
        raw_job = JobPostingRaw(
            source="jsearch",
            payload=SAMPLE_JSEARCH_RESPONSE["data"][0],
            provider_job_id="test-job-1",
        )

        # Map to common format
        common = adapter.map_to_common(raw_job)

        # Verify required fields
        assert common["job_title"] == "Senior Software Engineer"
        assert common["company"] == "TechCorp Inc"
        assert common["location"] == "San Francisco, CA, US"
        assert common["source"] == "jsearch"

        # Verify optional fields
        assert common["description"] == "We are looking for a talented software engineer..."
        assert common["url"] == "https://example.com/apply/123"
        assert common["posted_date"] == "2024-01-01T00:00:00.000Z"
        assert common["employment_type"] == "Full-time"
        assert common["salary_min"] == 120000
        assert common["salary_max"] == 180000
        assert common["is_remote"] is True

    def test_map_to_common_minimal_data(self):
        """Test mapping with minimal job data."""
        adapter = JSearchAdapter(api_key="test-key")

        # Create JobPostingRaw with minimal data
        raw_job = JobPostingRaw(
            source="jsearch",
            payload={
                "job_id": "minimal-job",
                "job_title": "Developer",
                "employer_name": "Company",
            },
            provider_job_id="minimal-job",
        )

        # Map to common format
        common = adapter.map_to_common(raw_job)

        # Verify required fields
        assert common["job_title"] == "Developer"
        assert common["company"] == "Company"
        assert common["location"] == "Unknown"
        assert common["source"] == "jsearch"

        # Verify optional fields are None
        assert common["description"] is None
        assert common["url"] is None
        assert common["posted_date"] is None

    def test_map_to_common_employment_types(self):
        """Test employment type mapping."""
        adapter = JSearchAdapter(api_key="test-key")

        employment_type_tests = [
            ("FULLTIME", "Full-time"),
            ("PARTTIME", "Part-time"),
            ("CONTRACTOR", "Contract"),
            ("INTERN", "Internship"),
            ("UNKNOWN_TYPE", "UNKNOWN_TYPE"),  # Pass through unknown types
        ]

        for jsearch_type, expected_type in employment_type_tests:
            raw_job = JobPostingRaw(
                source="jsearch",
                payload={
                    "job_title": "Test",
                    "employer_name": "Test",
                    "job_employment_type": jsearch_type,
                },
                provider_job_id="test",
            )

            common = adapter.map_to_common(raw_job)
            assert common["employment_type"] == expected_type

    def test_map_to_common_location_formats(self):
        """Test different location format combinations."""
        adapter = JSearchAdapter(api_key="test-key")

        location_tests = [
            # (city, state, country, expected)
            ("Austin", "TX", "US", "Austin, TX, US"),
            ("Austin", None, "US", "Austin, US"),
            (None, "TX", "US", "TX, US"),
            (None, None, "US", "US"),
            (None, None, None, "Unknown"),
        ]

        for city, state, country, expected in location_tests:
            payload = {
                "job_title": "Test",
                "employer_name": "Test",
            }
            if city:
                payload["job_city"] = city
            if state:
                payload["job_state"] = state
            if country:
                payload["job_country"] = country

            raw_job = JobPostingRaw(
                source="jsearch",
                payload=payload,
                provider_job_id="test",
            )

            common = adapter.map_to_common(raw_job)
            assert common["location"] == expected


class TestJSearchAdapterValidation:
    """Test validation and error handling."""

    def test_validate_common_format_success(self):
        """Test validation passes for valid data."""
        adapter = JSearchAdapter(api_key="test-key")

        valid_data = {
            "job_title": "Engineer",
            "company": "TechCorp",
            "location": "NYC",
            "source": "jsearch",
        }

        assert adapter.validate_common_format(valid_data) is True

    def test_validate_common_format_missing_fields(self):
        """Test validation fails for missing required fields."""
        adapter = JSearchAdapter(api_key="test-key")

        invalid_data = {
            "job_title": "Engineer",
            "company": "TechCorp",
            # Missing location and source
        }

        assert adapter.validate_common_format(invalid_data) is False

