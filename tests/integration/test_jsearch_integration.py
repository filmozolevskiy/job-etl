"""
Integration tests for JSearch adapter and database storage.

These tests verify the full flow from API to database, using a real
PostgreSQL database connection. Tests should be run against a test database.
"""

import os
from datetime import datetime
from unittest.mock import Mock, patch

import psycopg2
import pytest

from services.source_extractor.adapters.jsearch_adapter import JSearchAdapter
from services.source_extractor.base import JobPostingRaw
from services.source_extractor.db_storage import JobStorage, JobStorageError


# Sample job data for testing
SAMPLE_JOB_PAYLOAD = {
    "job_id": "integration-test-job-1",
    "employer_name": "Integration Test Corp",
    "job_title": "Integration Test Engineer",
    "job_city": "Test City",
    "job_state": "TC",
    "job_country": "US",
    "job_employment_type": "FULLTIME",
    "job_description": "This is a test job posting for integration tests",
    "job_is_remote": True,
}


@pytest.fixture
def database_url():
    """Get database URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set - integration tests require database")
    return db_url


@pytest.fixture
def job_storage(database_url):
    """Create JobStorage instance with context manager."""
    with JobStorage(database_url) as storage:
        yield storage


@pytest.fixture
def clean_test_data(database_url):
    """Clean up test data before and after tests."""
    # Cleanup function
    def cleanup():
        try:
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            # Delete test jobs
            cursor.execute(
                "DELETE FROM raw.job_postings_raw WHERE source = 'jsearch' OR source = 'test'"
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not clean test data: {e}")

    # Clean before test
    cleanup()

    # Yield control to test
    yield

    # Clean after test
    cleanup()


class TestJobStorageConnection:
    """Test database connection management."""

    def test_connect_with_valid_url(self, database_url, clean_test_data):
        """Test successful database connection."""
        storage = JobStorage(database_url)

        # Initially not connected
        assert storage.connection is None

        # Connect
        storage.connect()

        # Should be connected
        assert storage.connection is not None
        assert storage.cursor is not None

        # Cleanup
        storage.disconnect()

    def test_connect_with_invalid_url(self):
        """Test connection failure with invalid URL."""
        storage = JobStorage("postgresql://invalid:invalid@localhost:9999/invalid")

        with pytest.raises(JobStorageError, match="Database connection failed"):
            storage.connect()

    def test_context_manager(self, database_url, clean_test_data):
        """Test using JobStorage as context manager."""
        with JobStorage(database_url) as storage:
            assert storage.connection is not None
            assert storage.cursor is not None

        # After context, should be disconnected
        # (we can't check directly, but no errors should occur)


class TestJobStorageSaveJob:
    """Test saving individual jobs to database."""

    def test_save_single_job(self, job_storage, clean_test_data):
        """Test saving a single job posting."""
        # Create test job
        job = JobPostingRaw(
            source="test",
            payload=SAMPLE_JOB_PAYLOAD,
            provider_job_id="integration-test-job-1",
        )

        # Save job
        raw_id = job_storage.save_job(job)

        # Verify UUID was returned
        assert raw_id is not None
        assert len(raw_id) == 36  # UUID format

        # Verify job was saved
        count = job_storage.get_job_count_by_source("test")
        assert count == 1

    def test_save_job_with_custom_timestamp(self, job_storage, clean_test_data):
        """Test saving job with custom collected_at timestamp."""
        job = JobPostingRaw(
            source="test",
            payload=SAMPLE_JOB_PAYLOAD,
            provider_job_id="test-job-timestamp",
        )

        custom_time = datetime(2024, 1, 15, 12, 0, 0)
        raw_id = job_storage.save_job(job, collected_at=custom_time)

        assert raw_id is not None

    def test_save_job_without_connection_raises_error(self, database_url):
        """Test that saving without connection raises error."""
        storage = JobStorage(database_url)
        # Don't connect

        job = JobPostingRaw(
            source="test",
            payload=SAMPLE_JOB_PAYLOAD,
            provider_job_id="test-job",
        )

        with pytest.raises(JobStorageError, match="Not connected to database"):
            storage.save_job(job)


class TestJobStorageBatchSave:
    """Test batch saving of jobs."""

    def test_save_jobs_batch(self, job_storage, clean_test_data):
        """Test saving multiple jobs in a batch."""
        # Create multiple test jobs
        jobs = [
            JobPostingRaw(
                source="test",
                payload={**SAMPLE_JOB_PAYLOAD, "job_id": f"batch-job-{i}"},
                provider_job_id=f"batch-job-{i}",
            )
            for i in range(5)
        ]

        # Save batch
        raw_ids = job_storage.save_jobs_batch(jobs)

        # Verify all jobs were saved
        assert len(raw_ids) == 5
        assert all(len(rid) == 36 for rid in raw_ids)  # All UUIDs

        # Verify count in database
        count = job_storage.get_job_count_by_source("test")
        assert count == 5

    def test_save_empty_batch(self, job_storage, clean_test_data):
        """Test saving empty batch returns empty list."""
        raw_ids = job_storage.save_jobs_batch([])

        assert raw_ids == []

    def test_save_batch_without_connection_raises_error(self, database_url):
        """Test that batch saving without connection raises error."""
        storage = JobStorage(database_url)
        # Don't connect

        jobs = [
            JobPostingRaw(
                source="test",
                payload=SAMPLE_JOB_PAYLOAD,
                provider_job_id="test-job",
            )
        ]

        with pytest.raises(JobStorageError, match="Not connected to database"):
            storage.save_jobs_batch(jobs)


class TestJobStorageQueryMethods:
    """Test query methods for job counts."""

    def test_get_job_count_all_sources(self, job_storage, clean_test_data):
        """Test getting total job count across all sources."""
        # Save jobs from different sources
        job1 = JobPostingRaw(source="test1", payload=SAMPLE_JOB_PAYLOAD)
        job2 = JobPostingRaw(source="test2", payload=SAMPLE_JOB_PAYLOAD)

        job_storage.save_job(job1)
        job_storage.save_job(job2)

        # Get total count
        total_count = job_storage.get_job_count_by_source(None)
        assert total_count >= 2  # At least our test jobs

    def test_get_job_count_by_source(self, job_storage, clean_test_data):
        """Test getting job count filtered by source."""
        # Save jobs from different sources
        job1 = JobPostingRaw(source="test_source_1", payload=SAMPLE_JOB_PAYLOAD)
        job2 = JobPostingRaw(source="test_source_1", payload=SAMPLE_JOB_PAYLOAD)
        job3 = JobPostingRaw(source="test_source_2", payload=SAMPLE_JOB_PAYLOAD)

        job_storage.save_job(job1)
        job_storage.save_job(job2)
        job_storage.save_job(job3)

        # Get counts by source
        count_source_1 = job_storage.get_job_count_by_source("test_source_1")
        count_source_2 = job_storage.get_job_count_by_source("test_source_2")

        assert count_source_1 == 2
        assert count_source_2 == 1

    def test_get_job_count_without_connection_raises_error(self, database_url):
        """Test that querying without connection raises error."""
        storage = JobStorage(database_url)
        # Don't connect

        with pytest.raises(JobStorageError, match="Not connected to database"):
            storage.get_job_count_by_source("test")


class TestFullIntegrationFlow:
    """Test the complete flow from adapter to database."""

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_and_save_flow(self, mock_get, job_storage, clean_test_data):
        """Test full flow: fetch from API (mocked) and save to database."""
        # Setup mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "data": [
                {
                    "job_id": "flow-test-1",
                    "employer_name": "Flow Test Corp",
                    "job_title": "Flow Test Engineer",
                    "job_city": "Seattle",
                    "job_state": "WA",
                    "job_country": "US",
                },
                {
                    "job_id": "flow-test-2",
                    "employer_name": "Flow Test Inc",
                    "job_title": "Flow Test Developer",
                    "job_city": "Portland",
                    "job_state": "OR",
                    "job_country": "US",
                },
            ],
        }
        mock_get.return_value = mock_response

        # Create adapter and fetch jobs
        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)
        jobs, next_page = adapter.fetch()

        # Verify fetch results
        assert len(jobs) == 2
        assert all(isinstance(job, JobPostingRaw) for job in jobs)

        # Save jobs to database
        raw_ids = job_storage.save_jobs_batch(jobs, collected_at=datetime.utcnow())

        # Verify save results
        assert len(raw_ids) == 2

        # Verify jobs are in database
        count = job_storage.get_job_count_by_source("jsearch")
        assert count == 2

    @patch("services.source_extractor.adapters.jsearch_adapter.requests.get")
    def test_fetch_map_and_save_flow(self, mock_get, job_storage, clean_test_data):
        """Test full flow including data mapping."""
        # Setup mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "data": [
                {
                    "job_id": "map-test-1",
                    "employer_name": "Map Test Corp",
                    "job_title": "Senior Engineer",
                    "job_city": "Austin",
                    "job_state": "TX",
                    "job_country": "US",
                    "job_employment_type": "FULLTIME",
                    "job_is_remote": True,
                    "job_description": "Test description",
                },
            ],
        }
        mock_get.return_value = mock_response

        # Create adapter and fetch
        adapter = JSearchAdapter(api_key="test-key", max_jobs=20)
        jobs, _ = adapter.fetch()

        # Map to common format
        mapped_jobs = [adapter.map_to_common(job) for job in jobs]

        # Verify mapping
        assert len(mapped_jobs) == 1
        assert mapped_jobs[0]["job_title"] == "Senior Engineer"
        assert mapped_jobs[0]["company"] == "Map Test Corp"
        assert mapped_jobs[0]["location"] == "Austin, TX, US"
        assert mapped_jobs[0]["employment_type"] == "Full-time"
        assert mapped_jobs[0]["is_remote"] is True

        # Save original raw jobs
        raw_ids = job_storage.save_jobs_batch(jobs)

        # Verify save
        assert len(raw_ids) == 1
        count = job_storage.get_job_count_by_source("jsearch")
        assert count == 1


class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_save_rollback_on_error(self, database_url, clean_test_data):
        """Test that transactions are rolled back on error."""
        with JobStorage(database_url) as storage:
            # Save a valid job
            job1 = JobPostingRaw(source="test", payload=SAMPLE_JOB_PAYLOAD)
            storage.save_job(job1)

            initial_count = storage.get_job_count_by_source("test")

            # Try to save an invalid job (this should fail)
            # Create a job with invalid payload that might cause issues
            invalid_job = JobPostingRaw(
                source="test",
                payload=None,  # Invalid - should be a dict
            )

            try:
                storage.save_job(invalid_job)
            except (JobStorageError, Exception):
                pass  # Expected to fail

            # Count should be unchanged (transaction rolled back)
            final_count = storage.get_job_count_by_source("test")
            assert final_count == initial_count

    def test_multiple_saves_in_same_connection(self, job_storage, clean_test_data):
        """Test multiple save operations using same connection."""
        # Save multiple jobs individually
        for i in range(3):
            job = JobPostingRaw(
                source="test",
                payload={**SAMPLE_JOB_PAYLOAD, "job_id": f"multi-save-{i}"},
            )
            raw_id = job_storage.save_job(job)
            assert raw_id is not None

        # Verify all saved
        count = job_storage.get_job_count_by_source("test")
        assert count == 3

