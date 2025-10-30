"""
Example integration tests.

Integration tests verify that multiple components work together correctly.
They may require external services (database, APIs) and are typically slower.

To run these tests:
    pytest tests/integration/ -v
"""

import pytest


@pytest.mark.skip(reason="Integration tests disabled - requires dedicated test database")
def test_database_connection_placeholder():
    """
    Placeholder for database connection test.

    When we implement the database layer, this will test:
    - Connection to PostgreSQL
    - Schema existence (raw, staging, marts)
    - Ability to insert/query data
    
    See: docs/testing-setup.md for setup instructions
    """
    pass


@pytest.mark.skip(reason="Integration tests disabled - requires dedicated test database")
def test_end_to_end_pipeline_placeholder():
    """
    Placeholder for end-to-end pipeline test.

    Future implementation will test:
    1. Extract: Mock API response
    2. Normalize: Transform to canonical format
    3. Enrich: Add skills, standardize fields
    4. Rank: Calculate scores
    5. Publish: Generate Hyper file

    This is the "golden path" test that verifies the whole system works.
    
    See: docs/testing-setup.md for setup instructions
    """
    pass


@pytest.mark.skip(reason="Integration tests disabled - requires dedicated test database")
@pytest.mark.slow
def test_airflow_dag_validation_placeholder():
    """
    Placeholder for Airflow DAG validation test.

    Future implementation will:
    - Import the DAG
    - Validate task dependencies
    - Check for cycles
    - Verify task configuration
    
    See: docs/testing-setup.md for setup instructions
    """
    pass


# ============================================================================
# Mark all tests as integration tests
# ============================================================================

pytestmark = pytest.mark.integration