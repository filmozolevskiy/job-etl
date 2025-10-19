"""Source Adapter Base Class.

This module defines the abstract interface that all job posting API adapters must implement.
This ensures consistency across different data sources and makes it easy to add new providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class JobPostingRaw:
    """Raw job posting data from an API provider.

    This is a simple container for the raw JSON response and metadata.
    The actual job data structure varies by provider, so we store it as a dict.
    """

    source: str  # Provider name (e.g., "rapidapi_jsearch")
    payload: Dict[str, Any]  # Raw JSON response from API
    provider_job_id: Optional[str] = None  # Provider's unique job ID (if available)


class SourceAdapter(ABC):
    """Abstract base class for job posting API adapters.

    All job posting data sources must implement this interface. This ensures:
    - Consistent fetching mechanism across providers
    - Standard data transformation to our canonical format
    - Built-in retry logic and error handling

    Usage:
        class MyProviderAdapter(SourceAdapter):
            def __init__(self, api_key: str):
                super().__init__(source_name="my_provider")
                self.api_key = api_key

            def fetch(self, page_token=None):
                # Implement API fetching logic
                ...

            def map_to_common(self, raw):
                # Map provider fields to our schema
                ...
    """

    def __init__(self, source_name: str):
        """Initialize the adapter.

        Args:
            source_name: Unique identifier for this data source
                        (e.g., "rapidapi_jsearch", "indeed_api")
        """
        self.source_name = source_name

    @abstractmethod
    def fetch(
        self, page_token: Optional[str] = None
    ) -> Tuple[List[JobPostingRaw], Optional[str]]:
        """Fetch job postings from the API.

        This method should handle:
        - Making HTTP requests to the API
        - Pagination (using page_token)
        - Rate limiting (respect API limits)
        - Error handling (API errors, network issues)

        Args:
            page_token: Token for pagination. None for the first page.
                       Format depends on the provider (cursor, offset, page number, etc.)

        Returns:
            A tuple of:
            - List of JobPostingRaw objects containing raw API responses
            - Next page token (None if no more pages or provider doesn't support pagination)

        Raises:
            ValueError: If API credentials are invalid
            ConnectionError: If unable to reach the API
            RuntimeError: If API returns an error response

        Example:
            jobs, next_token = adapter.fetch()
            while next_token:
                more_jobs, next_token = adapter.fetch(next_token)
                jobs.extend(more_jobs)
        """
        pass

    @abstractmethod
    def map_to_common(self, raw: JobPostingRaw) -> Dict[str, Any]:
        """Map provider-specific JSON to our canonical staging format.

        This method transforms the raw API response into a standardized format
        that matches the staging.job_postings_stg schema.

        Args:
            raw: JobPostingRaw object containing the provider's raw response

        Returns:
            Dictionary with keys matching staging.job_postings_stg columns:
            - provider_job_id: str | None
            - job_link: str | None
            - job_title: str
            - company: str
            - company_size: str | None (enum: see dbt seeds)
            - location: str
            - remote_type: str (enum: remote, hybrid, onsite, unknown)
            - contract_type: str (enum: full_time, part_time, contract, intern, temp, unknown)
            - salary_min: float | None
            - salary_max: float | None
            - salary_currency: str | None (ISO 4217 code)
            - description: str | None
            - skills_raw: list[str] | None
            - posted_at: str | None (ISO 8601 timestamp)
            - apply_url: str | None
            - source: str (automatically set to self.source_name)

        Example:
            raw = JobPostingRaw(
                source="rapidapi",
                payload={"jobTitle": "Data Engineer", "companyName": "Acme Corp"}
            )
            common = adapter.map_to_common(raw)
            # Returns: {"job_title": "Data Engineer", "company": "Acme Corp", ...}
        """
        pass

    def validate_common_format(self, data: Dict[str, Any]) -> bool:
        """Validate that the mapped data has required fields.

        This is a helper method to ensure map_to_common returns valid data.

        Args:
            data: Dictionary returned by map_to_common

        Returns:
            True if valid, False otherwise

        Example:
            mapped = self.map_to_common(raw)
            if not self.validate_common_format(mapped):
                raise ValueError("Invalid data format")
        """
        required_fields = {"job_title", "company", "location", "source"}
        return all(field in data for field in required_fields)

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(source='{self.source_name}')"

