"""
Pytest configuration and shared fixtures

This file contains test fixtures that can be used across all tests.
Fixtures are reusable components that set up test preconditions.

Learn more: https://docs.pytest.org/en/stable/fixture.html
"""

import os

import pytest


@pytest.fixture(scope="session")
def database_url() -> str:
    """
    Provide database URL for tests.

    Uses environment variable if set, otherwise falls back to test default.

    Scope: session (created once per test run)

    Returns:
        str: PostgreSQL connection URL
    """
    return os.getenv(
        "DATABASE_URL",
        "postgresql://airflow:airflow@localhost:5432/job_etl"
    )


@pytest.fixture(scope="function")
def sample_job_posting() -> dict:
    """
    Provide a sample job posting for testing.

    This fixture returns a typical job posting structure that can be used
    in unit tests without needing to call external APIs.

    Scope: function (created fresh for each test)

    Returns:
        dict: Sample job posting data
    """
    return {
        "job_title": "Data Engineer",
        "company": "Acme Corp",
        "location": "Montreal, QC, Canada",
        "remote_type": "hybrid",
        "contract_type": "full_time",
        "salary_min": 80000,
        "salary_max": 120000,
        "salary_currency": "CAD",
        "description": "We are seeking a Data Engineer with experience in Python, SQL, and Airflow.",
        "skills_raw": ["python", "sql", "airflow", "dbt"],
        "posted_at": "2025-10-15T10:00:00Z",
        "apply_url": "https://example.com/apply",
        "source": "test_api",
    }


@pytest.fixture(scope="function")
def sample_job_batch() -> list[dict]:
    """
    Provide a batch of sample job postings for testing.

    Useful for testing batch processing, deduplication, and ranking logic.

    Scope: function (created fresh for each test)

    Returns:
        list[dict]: List of sample job postings
    """
    return [
        {
            "job_title": "Data Engineer",
            "company": "Acme Corp",
            "location": "Montreal, QC",
            "salary_min": 80000,
            "salary_max": 120000,
        },
        {
            "job_title": "Senior Data Engineer",
            "company": "Globex Inc",
            "location": "Toronto, ON",
            "salary_min": 100000,
            "salary_max": 150000,
        },
        {
            "job_title": "Analytics Engineer",
            "company": "Initech LLC",
            "location": "Remote",
            "salary_min": 90000,
            "salary_max": 130000,
        },
    ]


# Mark tests based on their type for selective running
def pytest_configure(config):
    """
    Register custom pytest markers.

    This allows us to run specific test categories:
    - pytest -m unit        (run only unit tests)
    - pytest -m integration (run only integration tests)
    - pytest -m "not slow"  (skip slow tests)
    """
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test (isolated, fast)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (requires services)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running (>1 second)"
    )

