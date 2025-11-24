"""
Glassdoor API Client for company enrichment.

This client connects to the OpenWebNinja Glassdoor API to fetch company information.
API Documentation: docs/Glassdoor_Data_ API_Documentation.md
"""

import logging
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# Constants
API_TIMEOUT_SECONDS = 30
DEFAULT_BASE_URL = "https://api.openwebninja.com"
DEFAULT_LIMIT = 10


class GlassdoorClient:
    """
    Client for Glassdoor Company Search API.

    Fetches company information from the Glassdoor API via OpenWebNinja.

    Environment Variables:
        GLASSDOOR_API_KEY: Your OpenWebNinja API key
        GLASSDOOR_BASE_URL: Base URL for the API (default: https://api.openwebninja.com)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Glassdoor client.

        Args:
            api_key: OpenWebNinja API key (defaults to GLASSDOOR_API_KEY env var)
            base_url: API base URL (defaults to GLASSDOOR_BASE_URL env var or default)
        """
        import os

        self.api_key = api_key or os.getenv("GLASSDOOR_API_KEY")
        configured_base = base_url or os.getenv("GLASSDOOR_BASE_URL", DEFAULT_BASE_URL)
        self.base_url = configured_base.rstrip("/")

        if not self.api_key:
            raise ValueError(
                "GLASSDOOR_API_KEY must be set in environment or passed as parameter"
            )

    def search_company(self, query: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
        """
        Search for companies using the Glassdoor API.

        Args:
            query: Company name or search query
            limit: Maximum number of results (1-100, default: 10)

        Returns:
            List of company objects from API response value.data, or empty list on error

        Raises:
            requests.exceptions.RequestException: On network/connection errors
        """
        endpoint = "/realtime-glassdoor-data/company-search"
        url = f"{self.base_url}{endpoint}"

        headers = {
            "x-api-key": self.api_key,  # Note: lowercase header name
            "Content-Type": "application/json",
        }

        params = {
            "query": query,
            "limit": min(max(1, limit), 100),  # Clamp between 1 and 100
        }

        logger.debug(
            "Making Glassdoor API call",
            extra={
                "endpoint": endpoint,
                "query": query,
                "limit": params["limit"],
            },
        )

        try:
            response = requests.get(
                url, headers=headers, params=params, timeout=API_TIMEOUT_SECONDS
            )

            # Handle HTTP errors with specific logging and custom messages
            if response.status_code == 401:
                logger.error("Invalid API key - check GLASSDOOR_API_KEY")
                raise requests.exceptions.HTTPError(
                    "Invalid API key - check GLASSDOOR_API_KEY"
                )
            elif response.status_code == 429:
                logger.error("Rate limit exceeded - too many API calls")
                raise requests.exceptions.HTTPError(
                    "Rate limit exceeded - too many API calls"
                )
            elif response.status_code >= 400:
                logger.error(
                    "API error %s: %s", response.status_code, response.text[:200]
                )
                raise requests.exceptions.HTTPError(
                    f"API error {response.status_code}: {response.text[:200]}"
                )

            try:
                data = response.json()
            except ValueError:
                logger.error(
                    "Failed to parse JSON response",
                    extra={"query": query, "response_text": response.text[:500]},
                )
                return []

            # Extract companies from API response
            # Actual response format: {"status": "OK", "data": [...]}
            # (Some API versions may wrap in {"value": {...}} but actual sandbox returns flat structure)
            if not isinstance(data, dict):
                logger.warning(
                    "API response is not a dict",
                    extra={
                        "query": query,
                        "response_type": type(data).__name__,
                        "response_preview": str(data)[:200],
                    },
                )
                return []

            # Try flat structure first (actual API response)
            if "data" in data:
                companies = data["data"]
                if isinstance(companies, list):
                    status = data.get("status", "")
                    logger.info(
                        "Glassdoor API call successful",
                        extra={
                            "query": query,
                            "status_code": response.status_code,
                            "status": status,
                            "companies_returned": len(companies),
                        },
                    )
                    return companies
                else:
                    logger.warning(
                        "API data field is not a list",
                        extra={"query": query, "data_type": type(companies).__name__},
                    )
            # Fallback: try nested "value" structure (documentation example)
            elif "value" in data and isinstance(data["value"], dict):
                value_obj = data["value"]
                if "data" in value_obj:
                    companies = value_obj["data"]
                    if isinstance(companies, list):
                        logger.info(
                            "Glassdoor API call successful (nested structure)",
                            extra={
                                "query": query,
                                "status_code": response.status_code,
                                "companies_returned": len(companies),
                            },
                        )
                        return companies

            # Log what we actually got
            logger.warning(
                "API response missing 'data' field",
                extra={
                    "query": query,
                    "response_keys": list(data.keys()),
                    "response_preview": str(data)[:500],
                },
            )
            return []

        except requests.exceptions.RequestException as exc:
            logger.error(
                "Glassdoor API request failed",
                extra={"query": query, "error": str(exc)},
            )
            return []

