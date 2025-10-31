"""
Integration Tests for JSearch Adapter - PLACEHOLDER

⚠️  THESE TESTS ARE CURRENTLY DISABLED FOR SAFETY

Why disabled:
- Integration tests require a real PostgreSQL database
- They DELETE data from raw.job_postings_raw matching test sources
- Risk of accidentally deleting development data

When to enable:
1. Set up a dedicated test database (see docs/testing-setup.md)
2. Configure DATABASE_URL to point to test database
3. Restore original tests from git history
4. Run: pytest tests/integration/test_jsearch_integration.py -v

For now, we rely on:
- Unit tests with mocked responses - Safe, fast, no database needed
- Manual testing with sample API calls
- Development environment testing

TODO: Enable integration tests once test database is configured
See: docs/testing-setup.md for setup instructions
"""

import pytest


@pytest.mark.skip(reason="Integration tests disabled - requires dedicated test database")
def test_jsearch_integration_placeholder():
    """
    Placeholder for JSearch adapter integration tests.
    
    Tests to implement when ready:
    
    Database Connection Management:
    - test_connect_with_valid_url: Test successful connection
    - test_connect_with_invalid_url: Test connection failure handling
    - test_context_manager: Test using JobStorage as context manager
    
    Saving Jobs:
    - test_save_single_job: Test saving individual job to database
    - test_save_job_with_custom_timestamp: Test custom timestamps
    - test_save_job_without_connection_raises_error: Test error handling
    - test_save_batch_without_connection_raises_error: Test batch errors
    
    Batch Operations:
    - test_save_batch: Test batch saving multiple jobs
    - test_save_empty_batch: Test empty batch handling
    
    Querying:
    - test_get_job_count_all_sources: Test counting all jobs
    - test_get_job_count_by_source: Test counting by source
    - test_get_job_count_without_connection_raises_error: Test error handling
    
    End-to-End Flow:
    - test_full_flow_fetch_and_save: Test API fetch → database save
    - test_save_rollback_on_error: Test transaction rollback
    - test_multiple_saves_in_same_connection: Test connection reuse
    
    Setup Instructions:
    1. Create test database: createdb job_etl_test
    2. Run schema: psql -d job_etl_test -f db/schema.sql
    3. Set env: export DATABASE_URL="postgresql://...job_etl_test"
    4. Restore tests from git history
    5. Run: pytest tests/integration/test_jsearch_integration.py -v
    
    Safety Note:
    These tests delete data WHERE:
      - source = 'jsearch' OR
      - source LIKE 'test%' OR
      - provider_job_id LIKE 'test_%'
    
    Reference:
    - Unit tests: tests/unit/test_jsearch_adapter.py (if exists)
    - Setup guide: docs/testing-setup.md
    - Git history: git log tests/integration/test_jsearch_integration.py
    """
    pass
