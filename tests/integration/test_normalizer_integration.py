"""
Integration Tests for Normalizer Service - PLACEHOLDER

⚠️  THESE TESTS ARE CURRENTLY DISABLED FOR SAFETY

Why disabled:
- Integration tests require a real PostgreSQL database
- They DELETE ALL DATA from raw.job_postings_raw and staging.job_postings_stg
- Risk of accidentally running against development database

When to enable:
1. Set up a dedicated test database (see docs/testing-setup.md)
2. Configure DATABASE_URL to point to test database
3. Restore original tests from git history or docs/testing-setup.md
4. Run: pytest tests/integration/test_normalizer_integration.py -v

For now, we rely on:
- Unit tests (tests/unit/test_normalizer.py) - Safe, fast, no database needed
- Manual testing with sample data
- End-to-end testing in development environment

TODO: Enable integration tests once test database is configured
See: docs/testing-setup.md for setup instructions
"""

import pytest


@pytest.mark.skip(reason="Integration tests disabled - requires dedicated test database")
def test_normalizer_integration_placeholder():
    """
    Placeholder for normalizer integration tests.

    Tests to implement when ready:

    Database Operations:
    - test_connection: Verify database connection and initialization
    - test_fetch_raw_jobs_empty: Test fetching from empty raw table
    - test_fetch_raw_jobs_with_data: Test fetching raw jobs after insert
    - test_upsert_staging_job_new: Test upserting new job to staging
    - test_upsert_staging_job_duplicate: Test idempotent upserts
    - test_upsert_staging_jobs_batch: Test batch upserting

    End-to-End Flow:
    - test_full_normalizer_flow: Test raw → normalize → staging
    - test_normalizer_idempotency: Test running twice on same data
    - test_normalizer_with_multiple_jobs: Test batch processing
    - test_normalizer_dry_run: Test dry run doesn't write
    - test_normalizer_with_invalid_data: Test error handling

    Data Quality:
    - test_hash_key_uniqueness: Test deduplication logic
    - test_enum_constraints: Test field validation

    Setup Instructions:
    1. Create test database: createdb job_etl_test
    2. Run schema: psql -d job_etl_test -f db/schema.sql
    3. Set env: export DATABASE_URL="postgresql://...job_etl_test"
    4. Restore tests from git history or docs/testing-setup.md
    5. Run: pytest tests/integration/test_normalizer_integration.py -v

    Reference:
    - Unit tests: tests/unit/test_normalizer.py
    - Setup guide: docs/testing-setup.md
    - Git history: git log tests/integration/test_normalizer_integration.py
    """
    pass
