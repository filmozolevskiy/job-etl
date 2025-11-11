"""
Unit tests for JSearch API Adapter.

These tests use mocked API responses to verify adapter behavior
without making real API calls.
"""

from contextlib import suppress
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
        "country": "US",
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
        assert adapter.country_code == "us"
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

        assert call_args[0][0] == f"{adapter.base_url}/jsearch/search"
        assert call_args[1]["params"]["query"] == "analytics engineer"
        assert call_args[1]["params"]["country"] == "us"
        assert call_args[1]["params"]["page"] == 1
        assert call_args[1]["headers"]["X-API-Key"] == "test-key"

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
    def test_fetch_normalizes_country_string(self, mock_get):
        """Country values are converted to ISO alpha-2 codes when possible."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_JSEARCH_RESPONSE
        mock_get.return_value = mock_response

        adapter = JSearchAdapter(api_key="test-key", country="Canada")
        adapter.fetch()

        call_args = mock_get.call_args
        assert call_args[1]["params"]["country"] == "ca"

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_preserves_iso_alpha2_country(self, mock_get):
        """Two-letter ISO country codes remain lowercase for API requests."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_JSEARCH_RESPONSE
        mock_get.return_value = mock_response

        adapter = JSearchAdapter(api_key="test-key", country="ca")
        adapter.fetch()

        call_args = mock_get.call_args
        assert call_args[1]["params"]["country"] == "ca"

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
        assert common["job_link"] == "https://example.com/apply/123"
        assert common["apply_url"] == "https://example.com/apply/123"
        assert common["posted_at"] == "2024-01-01T00:00:00.000Z"
        assert common["contract_type"] == "full_time"
        assert common["salary_min"] == 120000
        assert common["salary_max"] == 180000
        assert common["salary_currency"] == "USD"
        assert common["remote_type"] == "remote"
        assert common["provider_job_id"] == "test-job-1"

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
        assert common["remote_type"] == "unknown"
        assert common["contract_type"] == "unknown"

        # Verify optional fields are None
        assert common["description"] is None
        assert common["job_link"] is None
        assert common["apply_url"] is None
        assert common["posted_at"] is None
        assert common["salary_min"] is None
        assert common["salary_max"] is None
        assert common["skills_raw"] is None
        assert common["company_size"] is None

    def test_map_to_common_employment_types(self):
        """Test contract type mapping (formerly employment type)."""
        adapter = JSearchAdapter(api_key="test-key")

        contract_type_tests = [
            ("FULLTIME", "full_time"),
            ("PARTTIME", "part_time"),
            ("CONTRACTOR", "contract"),
            ("INTERN", "intern"),
            ("TEMPORARY", "temp"),
            ("UNKNOWN_TYPE", "unknown"),  # Unknown types map to "unknown"
        ]

        for jsearch_type, expected_type in contract_type_tests:
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
            assert common["contract_type"] == expected_type

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


class TestJSearchAdapterEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_malformed_json(self, mock_get):
        """Test handling of malformed JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        adapter = JSearchAdapter(api_key="test-key")

        with pytest.raises(ValueError, match="Invalid JSON"):
            adapter.fetch()

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_network_timeout(self, mock_get):
        """Test handling of network timeout."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        adapter = JSearchAdapter(api_key="test-key")

        # Should retry and eventually fail
        with pytest.raises(requests.exceptions.Timeout):
            adapter.fetch()

        # Verify retries occurred (1 initial + 3 retries = 4 total)
        assert mock_get.call_count == 4

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_connection_error(self, mock_get):
        """Test handling of connection errors."""
        mock_get.side_effect = ConnectionError("Failed to connect")

        adapter = JSearchAdapter(api_key="test-key")

        # Should retry and eventually fail
        with pytest.raises(ConnectionError):
            adapter.fetch()

        # Verify retries occurred (1 initial + 3 retries = 4 total)
        assert mock_get.call_count == 4

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_empty_data_array(self, mock_get):
        """Test handling of empty data array in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "data": [],  # Empty array
        }
        mock_get.return_value = mock_response

        adapter = JSearchAdapter(api_key="test-key")
        jobs, next_page = adapter.fetch()

        assert len(jobs) == 0
        assert next_page is None

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_missing_data_key(self, mock_get):
        """Test handling of missing 'data' key in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            # Missing 'data' key
        }
        mock_get.return_value = mock_response

        adapter = JSearchAdapter(api_key="test-key")
        jobs, next_page = adapter.fetch()

        assert len(jobs) == 0
        assert next_page is None

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_partial_job_data(self, mock_get):
        """Test handling of jobs with missing optional fields."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    # Minimal job data - only required fields
                    "job_id": "minimal-job",
                    "job_title": "Test Job",
                    "employer_name": "Test Company",
                    "job_country": "US",
                    # All other fields missing
                }
            ]
        }
        mock_get.return_value = mock_response

        adapter = JSearchAdapter(api_key="test-key")
        jobs, next_page = adapter.fetch()

        assert len(jobs) == 1
        assert jobs[0].provider_job_id == "minimal-job"
        assert jobs[0].payload["job_title"] == "Test Job"

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_api_call_count_with_retries(self, mock_get):
        """Test that API call count includes failed retry attempts."""
        # Fail twice, succeed on third attempt
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Internal Server Error"

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": []}

        mock_get.side_effect = [
            requests.exceptions.HTTPError("Server Error"),
            requests.exceptions.HTTPError("Server Error"),
            mock_response_success,
        ]

        adapter = JSearchAdapter(api_key="test-key")

        with suppress(requests.exceptions.HTTPError):
            adapter.fetch()

        # Should count all 3 attempts
        assert adapter.api_call_count == 3

    def test_configurable_search_parameters(self):
        """Test that search parameters can be customized."""
        adapter = JSearchAdapter(
            api_key="test-key",
            query="data scientist",
            country="Canada",
            date_posted="week",
        )

        assert adapter.query == "data scientist"
        assert adapter.country == "Canada"
        assert adapter.country_code == "ca"
        assert adapter.date_posted == "week"

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_pagination_cumulative_tracking(self, mock_get):
        """Test that pagination correctly tracks cumulative job count."""
        # Mock responses for multiple pages with varying sizes
        mock_response_page1 = Mock()
        mock_response_page1.status_code = 200
        mock_response_page1.json.return_value = {
            "data": [{"job_id": f"job-{i}"} for i in range(10)]  # 10 jobs
        }

        mock_response_page2 = Mock()
        mock_response_page2.status_code = 200
        mock_response_page2.json.return_value = {
            "data": [{"job_id": f"job-{i}"} for i in range(10, 18)]  # 8 jobs
        }

        mock_get.return_value = mock_response_page1

        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)
        jobs1, next_page1 = adapter.fetch()

        assert len(jobs1) == 10
        assert adapter.total_jobs_fetched == 10
        assert next_page1 == "2"

        mock_get.return_value = mock_response_page2
        jobs2, next_page2 = adapter.fetch(page_token="2")

        assert len(jobs2) == 8
        assert adapter.total_jobs_fetched == 18  # Cumulative count
        assert next_page2 == "3"  # Still has next page available

# ============================================================================
# Mark all tests as unit tests
# ============================================================================

pytestmark = pytest.mark.unit
