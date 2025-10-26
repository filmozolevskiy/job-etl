"""
JSearch API Adapter for OpenWebNinja job listings.

This adapter connects to the OpenWebNinja JSearch API to fetch real job postings.
API Documentation: services/source_extractor/adapters/jsearch_api_documentation.md
"""

import logging
import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from ..base import JobPostingRaw, SourceAdapter
from ..retry import retry_with_backoff

# Load environment variables from .env
load_dotenv()

logger = logging.getLogger(__name__)

# Constants
API_TIMEOUT_SECONDS = 30
DEFAULT_MAX_JOBS = 20
DEFAULT_QUERY = "analytics engineer"
DEFAULT_LOCATION = "United States"
DEFAULT_DATE_POSTED = "month"


class JSearchAdapter(SourceAdapter):
    """
    Adapter for JSearch API (OpenWebNinja).

    Fetches job postings from the JSearch API and maps them to our common format.

    Environment Variables Required:
        JSEARCH_API_KEY: Your OpenWebNinja API key
        JSEARCH_BASE_URL: Base URL for the API (default: https://api.openwebninja.com)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_jobs: int = DEFAULT_MAX_JOBS,
        query: str = DEFAULT_QUERY,
        location: str = DEFAULT_LOCATION,
        date_posted: str = DEFAULT_DATE_POSTED,
    ):
        """
        Initialize the JSearch adapter.

        Args:
            api_key: OpenWebNinja API key (defaults to JSEARCH_API_KEY env var)
            base_url: API base URL (defaults to JSEARCH_BASE_URL env var)
            max_jobs: Maximum number of jobs to fetch (default: 20)
            query: Job search query (default: "analytics engineer")
            location: Location filter (default: "United States")
            date_posted: Date filter - all/today/3days/week/month (default: "month")
        """
        super().__init__(source_name="jsearch")

        # Load configuration from environment or parameters
        self.api_key = api_key or os.getenv("JSEARCH_API_KEY")
        self.base_url = base_url or os.getenv(
            "JSEARCH_BASE_URL", "https://api.openwebninja.com"
        )
        self.max_jobs = max_jobs
        self.query = query
        self.location = location
        self.date_posted = date_posted

        # Validate API key
        if not self.api_key:
            raise ValueError(
                "JSEARCH_API_KEY must be set in environment or passed as parameter"
            )

        # Track API usage and pagination
        self.api_call_count = 0
        self.total_jobs_fetched = 0  # Track cumulative jobs across pages

        logger.info(
            "JSearch adapter initialized",
            extra={
                "source": self.source_name,
                "base_url": self.base_url,
                "max_jobs": self.max_jobs,
            },
        )

    @retry_with_backoff(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        exceptions=(requests.exceptions.RequestException, ConnectionError, TimeoutError),
    )
    def _make_api_call(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Make an API call to JSearch with retry logic.

        Args:
            endpoint: API endpoint (e.g., 'jsearch/search')
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.exceptions.RequestException: On API errors
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        # Track API usage (before request to count retries)
        self.api_call_count += 1

        logger.debug(
            "Making JSearch API call",
            extra={
                "endpoint": endpoint,
                "params": params,
                "call_count": self.api_call_count,
            },
        )

        response = requests.get(
            url, headers=headers, params=params, timeout=API_TIMEOUT_SECONDS
        )

        # Handle HTTP errors
        if response.status_code == 401:
            raise requests.exceptions.HTTPError(
                "Invalid API key - check JSEARCH_API_KEY"
            )
        elif response.status_code == 429:
            raise requests.exceptions.HTTPError(
                "Rate limit exceeded - too many API calls"
            )
        elif response.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"API error {response.status_code}: {response.text}"
            )

        data = response.json()

        logger.info(
            "JSearch API call successful",
            extra={
                "endpoint": endpoint,
                "status_code": response.status_code,
                "total_api_calls": self.api_call_count,
                "jobs_returned": len(data.get("data", [])),
            },
        )

        return data

    def fetch(
        self, page_token: Optional[str] = None
    ) -> tuple[list[JobPostingRaw], Optional[str]]:
        """
        Fetch job postings from JSearch API.

        Args:
            page_token: Page number as string (e.g., "1", "2", "3")

        Returns:
            Tuple of (list of JobPostingRaw objects, next_page_token)
            next_page_token is None if no more pages available

        Note:
            Search parameters (query, location, date_posted) are configured
            during adapter initialization.
        """
        # Determine current page
        current_page = int(page_token) if page_token else 1

        # Build search parameters from configuration
        params = {
            "query": self.query,
            "location": self.location,
            "page": current_page,
            "num_pages": 1,  # Fetch one page at a time
            "date_posted": self.date_posted,
        }

        logger.info(
            "Fetching jobs from JSearch",
            extra={
                "page": current_page,
                "query": params["query"],
                "location": params["location"],
                "date_posted": params["date_posted"],
            },
        )

        try:
            # Make API call
            response_data = self._make_api_call("jsearch/search", params)

            # Extract job data
            jobs_data = response_data.get("data", [])

            if not jobs_data:
                logger.warning("No jobs returned from API")
                return [], None

            # Convert to JobPostingRaw objects
            jobs = []
            for job_data in jobs_data:
                job = JobPostingRaw(
                    source=self.source_name,
                    payload=job_data,
                    provider_job_id=job_data.get("job_id"),
                )
                jobs.append(job)

            # Update cumulative count
            self.total_jobs_fetched += len(jobs)

            # Determine next page token
            # Continue pagination until we reach max_jobs or no more results
            next_page = None
            if self.total_jobs_fetched < self.max_jobs and jobs_data:
                next_page = str(current_page + 1)

            logger.info(
                "Successfully fetched jobs",
                extra={
                    "page": current_page,
                    "jobs_in_page": len(jobs),
                    "total_fetched_so_far": self.total_jobs_fetched,
                    "has_next_page": next_page is not None,
                    "total_api_calls": self.api_call_count,
                },
            )

            return jobs, next_page

        except requests.exceptions.RequestException as e:
            logger.error(
                "Failed to fetch jobs from JSearch",
                extra={
                    "page": current_page,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    def map_to_common(self, raw: JobPostingRaw) -> dict[str, Any]:
        """
        Map JSearch API response to our common format.

        Args:
            raw: JobPostingRaw object containing JSearch API response

        Returns:
            Dictionary matching staging.job_postings_stg schema with fields:
            - provider_job_id (str | None)
            - job_link (str | None)
            - job_title (str)
            - company (str)
            - company_size (str | None)
            - location (str)
            - remote_type (str: remote/hybrid/onsite/unknown)
            - contract_type (str: full_time/part_time/contract/intern/temp/unknown)
            - salary_min (float | None)
            - salary_max (float | None)
            - salary_currency (str | None)
            - description (str | None)
            - skills_raw (list[str] | None)
            - posted_at (str | None)
            - apply_url (str | None)
            - source (str)
        """
        payload = raw.payload

        # Build location string from available fields
        location_parts = []
        if payload.get("job_city"):
            location_parts.append(payload["job_city"])
        if payload.get("job_state"):
            location_parts.append(payload["job_state"])
        if payload.get("job_country"):
            location_parts.append(payload["job_country"])

        location = ", ".join(location_parts) if location_parts else "Unknown"

        # Map remote type to enum (remote, hybrid, onsite, unknown)
        if payload.get("job_is_remote"):
            remote_type = "remote"
        elif location != "Unknown":
            remote_type = "onsite"
        else:
            remote_type = "unknown"

        # Map employment type to contract_type enum
        contract_type_map = {
            "FULLTIME": "full_time",
            "PARTTIME": "part_time",
            "CONTRACTOR": "contract",
            "INTERN": "intern",
            "TEMPORARY": "temp",
        }
        contract_type = contract_type_map.get(
            payload.get("job_employment_type"), "unknown"
        )

        # Build common format matching staging.job_postings_stg schema
        common_data = {
            "provider_job_id": payload.get("job_id"),
            "job_link": payload.get("job_apply_link"),
            "job_title": payload.get("job_title", "Unknown Title"),
            "company": payload.get("employer_name", "Unknown Company"),
            "company_size": None,  # JSearch API doesn't provide this field
            "location": location,
            "remote_type": remote_type,
            "contract_type": contract_type,
            "salary_min": payload.get("job_min_salary"),
            "salary_max": payload.get("job_max_salary"),
            "salary_currency": payload.get("job_salary_currency", "USD"),
            "description": payload.get("job_description"),
            "skills_raw": None,  # Will be extracted by enricher service
            "posted_at": payload.get("job_posted_at_datetime_utc"),
            "apply_url": payload.get("job_apply_link"),
            "source": self.source_name,
        }

        # Validate the common format
        if not self.validate_common_format(common_data):
            logger.warning(
                "Mapped data failed validation",
                extra={
                    "job_id": raw.provider_job_id,
                    "missing_fields": [
                        f
                        for f in ["job_title", "company", "location", "source"]
                        if not common_data.get(f)
                    ],
                },
            )

        return common_data

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return (
            f"JSearchAdapter(source='{self.source_name}', "
            f"max_jobs={self.max_jobs}, "
            f"api_calls={self.api_call_count})"
        )

