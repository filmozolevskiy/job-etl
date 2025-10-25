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


class JSearchAdapter(SourceAdapter):
    """
    Adapter for JSearch API (OpenWebNinja).

    Fetches job postings from the JSearch API and maps them to our common format.

    Environment Variables Required:
        JSEARCH_API_KEY: Your OpenWebNinja API key
        JSEARCH_BASE_URL: Base URL for the API (default: https://api.openwebninja.com/v1)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_jobs: int = 20,
    ):
        """
        Initialize the JSearch adapter.

        Args:
            api_key: OpenWebNinja API key (defaults to JSEARCH_API_KEY env var)
            base_url: API base URL (defaults to JSEARCH_BASE_URL env var)
            max_jobs: Maximum number of jobs to fetch (default: 20)
        """
        super().__init__(source_name="jsearch")

        # Load configuration from environment or parameters
        self.api_key = api_key or os.getenv("JSEARCH_API_KEY")
        self.base_url = base_url or os.getenv(
            "JSEARCH_BASE_URL", "https://api.openwebninja.com"
        )
        self.max_jobs = max_jobs

        # Validate API key
        if not self.api_key:
            raise ValueError(
                "JSEARCH_API_KEY must be set in environment or passed as parameter"
            )

        # Track API usage
        self.api_call_count = 0

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

        logger.debug(
            "Making JSearch API call",
            extra={
                "endpoint": endpoint,
                "params": params,
                "call_count": self.api_call_count + 1,
            },
        )

        response = requests.get(url, headers=headers, params=params, timeout=30)

        # Track API usage
        self.api_call_count += 1

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

        response.raise_for_status()

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
            This implementation searches for "analytics engineer" jobs in the USA
            to get a diverse set of job postings for testing.
        """
        # Determine current page
        current_page = int(page_token) if page_token else 1

        # Search parameters - using a broad query to get diverse results
        params = {
            "query": "analytics engineer",
            "location": "United States",
            "page": current_page,
            "num_pages": 1,  # Fetch one page at a time
            "date_posted": "month",  # Recent jobs
        }

        logger.info(
            "Fetching jobs from JSearch",
            extra={
                "page": current_page,
                "query": params["query"],
                "location": params["location"],
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

            # Determine next page token
            # Continue pagination until we reach max_jobs or no more results
            total_fetched = current_page * len(jobs_data)
            next_page = None

            if total_fetched < self.max_jobs and jobs_data:
                next_page = str(current_page + 1)

            logger.info(
                "Successfully fetched jobs",
                extra={
                    "page": current_page,
                    "jobs_in_page": len(jobs),
                    "total_fetched_so_far": total_fetched,
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
            Dictionary in our canonical format with fields:
            - job_title
            - company
            - location
            - source
            - description (optional)
            - url (optional)
            - posted_date (optional)
            - employment_type (optional)
            - salary_min (optional)
            - salary_max (optional)
            - is_remote (optional)
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

        # Map employment type
        employment_type_map = {
            "FULLTIME": "Full-time",
            "PARTTIME": "Part-time",
            "CONTRACTOR": "Contract",
            "INTERN": "Internship",
        }
        employment_type = payload.get("job_employment_type")
        if employment_type:
            employment_type = employment_type_map.get(employment_type, employment_type)

        # Convert timestamp to ISO date string if available
        posted_date = None
        if payload.get("job_posted_at_datetime_utc"):
            posted_date = payload["job_posted_at_datetime_utc"]

        # Build common format
        common_data = {
            "job_title": payload.get("job_title", "Unknown Title"),
            "company": payload.get("employer_name", "Unknown Company"),
            "location": location,
            "source": self.source_name,
            "description": payload.get("job_description"),
            "url": payload.get("job_apply_link"),
            "posted_date": posted_date,
            "employment_type": employment_type,
            "salary_min": payload.get("job_min_salary"),
            "salary_max": payload.get("job_max_salary"),
            "is_remote": payload.get("job_is_remote", False),
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

