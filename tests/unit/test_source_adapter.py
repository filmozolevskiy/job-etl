"""Contract tests for SourceAdapter implementations.

These tests ensure that any implementation of SourceAdapter follows the interface contract.
They can be run against any adapter (MockAdapter, RealAPIAdapter, etc.) to verify compliance.
"""

import pytest

from services.source_extractor import JobPostingRaw, SourceAdapter
from services.source_extractor.adapters.mock_adapter import MockAdapter


class TestSourceAdapterContract:
    """Contract tests that all SourceAdapter implementations must pass."""

    @pytest.fixture
    def adapter(self) -> SourceAdapter:
        """Provide an adapter instance for testing.

        This fixture returns a MockAdapter by default, but can be overridden
        to test other adapter implementations.
        """
        return MockAdapter(num_jobs=50, jobs_per_page=10)

    def test_adapter_has_source_name(self, adapter: SourceAdapter):
        """Adapter must have a source_name attribute."""
        assert hasattr(adapter, "source_name")
        assert isinstance(adapter.source_name, str)
        assert len(adapter.source_name) > 0

    def test_fetch_returns_correct_type(self, adapter: SourceAdapter):
        """fetch() must return tuple of (list[JobPostingRaw], str | None)."""
        result = adapter.fetch()

        # Check return type
        assert isinstance(result, tuple)
        assert len(result) == 2

        jobs, next_token = result

        # Check jobs list
        assert isinstance(jobs, list)
        for job in jobs:
            assert isinstance(job, JobPostingRaw)

        # Check next_token
        assert next_token is None or isinstance(next_token, str)

    def test_fetch_returns_non_empty_first_page(self, adapter: SourceAdapter):
        """First call to fetch() should return at least one job."""
        jobs, _ = adapter.fetch()
        assert len(jobs) > 0, "First page should contain at least one job"

    def test_fetch_with_none_starts_at_beginning(self, adapter: SourceAdapter):
        """Calling fetch(None) should start from the first page."""
        jobs1, token1 = adapter.fetch(None)
        jobs2, token2 = adapter.fetch(None)

        # Both calls should return the same first page
        assert len(jobs1) == len(jobs2)

    def test_fetch_pagination_works(self):
        """Pagination should return different jobs on each page."""
        adapter = MockAdapter(num_jobs=30, jobs_per_page=10)

        # Fetch first page
        page1_jobs, token1 = adapter.fetch()
        assert len(page1_jobs) == 10
        assert token1 is not None

        # Fetch second page
        page2_jobs, token2 = adapter.fetch(token1)
        assert len(page2_jobs) == 10
        assert token2 is not None

        # Fetch third page
        page3_jobs, token3 = adapter.fetch(token2)
        assert len(page3_jobs) == 10
        assert token3 is None  # No more pages

        # Verify different jobs on each page
        page1_ids = {job.provider_job_id for job in page1_jobs}
        page2_ids = {job.provider_job_id for job in page2_jobs}
        page3_ids = {job.provider_job_id for job in page3_jobs}

        assert len(page1_ids & page2_ids) == 0, "Page 1 and 2 should have different jobs"
        assert len(page2_ids & page3_ids) == 0, "Page 2 and 3 should have different jobs"

    def test_fetch_last_page_returns_none_token(self):
        """Last page should return None as next_token."""
        adapter = MockAdapter(num_jobs=5, jobs_per_page=10)

        jobs, next_token = adapter.fetch()
        assert len(jobs) == 5
        assert next_token is None

    def test_job_posting_raw_structure(self, adapter: SourceAdapter):
        """JobPostingRaw objects must have required fields."""
        jobs, _ = adapter.fetch()
        job = jobs[0]

        # Check required fields
        assert hasattr(job, "source")
        assert hasattr(job, "payload")
        assert hasattr(job, "provider_job_id")

        # Check types
        assert isinstance(job.source, str)
        assert isinstance(job.payload, dict)
        assert job.provider_job_id is None or isinstance(job.provider_job_id, str)

    def test_map_to_common_returns_dict(self, adapter: SourceAdapter):
        """map_to_common() must return a dictionary."""
        jobs, _ = adapter.fetch()
        job = jobs[0]

        common = adapter.map_to_common(job)
        assert isinstance(common, dict)

    def test_map_to_common_has_required_fields(self, adapter: SourceAdapter):
        """map_to_common() must return dict with required fields."""
        jobs, _ = adapter.fetch()
        job = jobs[0]

        common = adapter.map_to_common(job)

        # Required fields that must not be None
        required_fields = {
            "job_title": str,
            "company": str,
            "location": str,
            "source": str,
        }

        for field, expected_type in required_fields.items():
            assert field in common, f"Missing required field: {field}"
            assert isinstance(
                common[field], expected_type
            ), f"{field} must be {expected_type.__name__}"
            assert len(common[field]) > 0, f"{field} must not be empty"

    def test_map_to_common_has_optional_fields(self, adapter: SourceAdapter):
        """map_to_common() should include optional fields (can be None)."""
        jobs, _ = adapter.fetch()
        job = jobs[0]

        common = adapter.map_to_common(job)

        # Optional fields
        optional_fields = [
            "provider_job_id",
            "job_link",
            "company_size",
            "remote_type",
            "contract_type",
            "salary_min",
            "salary_max",
            "salary_currency",
            "description",
            "skills_raw",
            "posted_at",
            "apply_url",
        ]

        for field in optional_fields:
            assert field in common, f"Missing optional field: {field}"

    def test_map_to_common_remote_type_enum(self, adapter: SourceAdapter):
        """remote_type must be one of the allowed enum values."""
        jobs, _ = adapter.fetch()
        job = jobs[0]

        common = adapter.map_to_common(job)

        valid_remote_types = {"remote", "hybrid", "onsite", "unknown"}
        remote_type = common.get("remote_type")

        if remote_type is not None:
            assert (
                remote_type in valid_remote_types
            ), f"Invalid remote_type: {remote_type}"

    def test_map_to_common_contract_type_enum(self, adapter: SourceAdapter):
        """contract_type must be one of the allowed enum values."""
        jobs, _ = adapter.fetch()
        job = jobs[0]

        common = adapter.map_to_common(job)

        valid_contract_types = {
            "full_time",
            "part_time",
            "contract",
            "intern",
            "temp",
            "unknown",
        }
        contract_type = common.get("contract_type")

        if contract_type is not None:
            assert (
                contract_type in valid_contract_types
            ), f"Invalid contract_type: {contract_type}"

    def test_validate_common_format_accepts_valid_data(self, adapter: SourceAdapter):
        """validate_common_format() should accept valid mapped data."""
        jobs, _ = adapter.fetch()
        job = jobs[0]

        common = adapter.map_to_common(job)
        assert adapter.validate_common_format(common)

    def test_validate_common_format_rejects_missing_fields(self, adapter: SourceAdapter):
        """validate_common_format() should reject data missing required fields."""
        # Missing 'company'
        invalid_data = {
            "job_title": "Engineer",
            "location": "Montreal",
            "source": "test",
        }
        assert not adapter.validate_common_format(invalid_data)

    def test_adapter_repr(self, adapter: SourceAdapter):
        """Adapter should have a useful string representation."""
        repr_str = repr(adapter)
        assert isinstance(repr_str, str)
        assert adapter.source_name in repr_str


class TestMockAdapter:
    """Tests specific to MockAdapter implementation."""

    def test_mock_adapter_generates_exact_number_of_jobs(self):
        """MockAdapter should generate exactly the specified number of jobs."""
        adapter = MockAdapter(num_jobs=100, jobs_per_page=20)

        all_jobs = []
        next_token = None

        # Fetch all pages
        while True:
            jobs, next_token = adapter.fetch(next_token)
            all_jobs.extend(jobs)
            if next_token is None:
                break

        assert len(all_jobs) == 100

    def test_mock_adapter_respects_jobs_per_page(self):
        """MockAdapter should return the correct number of jobs per page."""
        adapter = MockAdapter(num_jobs=100, jobs_per_page=15)

        jobs, next_token = adapter.fetch()
        assert len(jobs) == 15
        assert next_token is not None

    def test_mock_adapter_generates_unique_jobs(self):
        """MockAdapter should generate unique job IDs."""
        adapter = MockAdapter(num_jobs=50, jobs_per_page=50)

        jobs, _ = adapter.fetch()
        job_ids = [job.provider_job_id for job in jobs]

        # All IDs should be unique
        assert len(job_ids) == len(set(job_ids))

    def test_mock_adapter_can_simulate_failures(self):
        """MockAdapter can simulate API failures for testing retry logic."""
        adapter = MockAdapter(num_jobs=10, fail_on_attempt=1)

        # First attempt should fail
        with pytest.raises(ConnectionError, match="Simulated API failure"):
            adapter.fetch()

        # Reset attempt counter
        adapter.attempt_count = 0
        adapter.fail_on_attempt = 0

        # Should succeed now
        jobs, _ = adapter.fetch()
        assert len(jobs) > 0

# ============================================================================
# Mark all tests as unit tests
# ============================================================================

pytestmark = pytest.mark.unit
