"""
Company name matcher using fuzzy string matching.

Matches company names from job postings to Glassdoor API results using
rapidfuzz for fuzzy string matching.
"""

import logging
import re
from typing import Optional

from rapidfuzz import fuzz

from .glassdoor_client import GlassdoorClient

logger = logging.getLogger(__name__)

# Default similarity threshold (80%)
DEFAULT_SIMILARITY_THRESHOLD = 80

# Common company suffixes to remove during normalization
# Note: "Company" is not included as it's often part of the actual company name
COMPANY_SUFFIXES = [
    r"\bInc\.?\b",
    r"\bLLC\.?\b",
    r"\bLtd\.?\b",
    r"\bCorp\.?\b",
    r"\bCorporation\b",
    r"\bCo\.?\b",
    r"\bLP\.?\b",
    r"\bLLP\.?\b",
    r"\bPC\.?\b",
    r"\bP\.C\.\b",
    r"\bPLLC\.?\b",
    r"\bPLC\.?\b",
    r"\bGmbH\b",
    r"\bAG\b",
    r"\bSA\b",
    r"\bS\.A\.\b",
    r"\bS\.L\.\b",
    r"\bS\.R\.L\.\b",
]


class CompanyMatcher:
    """
    Matches company names to Glassdoor API results using fuzzy matching.

    Normalizes company names by removing common suffixes and extra whitespace,
    then uses rapidfuzz to find the best match from Glassdoor API results.
    """

    def __init__(
        self,
        glassdoor_client: GlassdoorClient,
        similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD,
    ):
        """
        Initialize the company matcher.

        Args:
            glassdoor_client: GlassdoorClient instance for API calls
            similarity_threshold: Minimum similarity score (0-100) to accept a match
        """
        self.client = glassdoor_client
        self.threshold = similarity_threshold

    def normalize_company_name(self, name: str) -> str:
        """
        Normalize a company name for matching.

        Removes common suffixes, extra whitespace, and converts to lowercase.

        Args:
            name: Raw company name

        Returns:
            Normalized company name
        """
        if not name or not isinstance(name, str):
            return ""

        # Convert to lowercase and strip whitespace
        normalized = name.lower().strip()

        # Remove common company suffixes
        for suffix_pattern in COMPANY_SUFFIXES:
            normalized = re.sub(suffix_pattern, "", normalized, flags=re.IGNORECASE)

        # Remove extra whitespace and trailing punctuation
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = re.sub(r"\s*[.\s]+\s*$", "", normalized).strip()  # Remove trailing periods/spaces

        return normalized

    def match_company(self, company_name: str) -> Optional[dict]:
        """
        Find the best matching company from Glassdoor API.

        Args:
            company_name: Company name to search for

        Returns:
            Best matching company dict from API, or None if no good match found
        """
        if not company_name or not company_name.strip():
            logger.debug("Empty company name provided for matching")
            return None

        # Search Glassdoor API
        try:
            results = self.client.search_company(company_name, limit=10)
        except Exception as exc:
            logger.error(
                "Failed to search Glassdoor API for company",
                extra={"company": company_name, "error": str(exc)},
            )
            return None

        if not results:
            logger.debug("No results from Glassdoor API", extra={"company": company_name})
            return None

        # Normalize input company name
        normalized_input = self.normalize_company_name(company_name)

        # Find best match using fuzzy string matching
        best_match = None
        best_score = 0

        for result in results:
            result_name = result.get("name", "")
            if not result_name:
                continue

            normalized_result = self.normalize_company_name(result_name)

            # Calculate similarity score
            score = fuzz.ratio(normalized_input, normalized_result)

            if score > best_score:
                best_score = score
                best_match = result

        # Check if best match meets threshold
        if best_match and best_score >= self.threshold:
            logger.debug(
                "Found company match",
                extra={
                    "input": company_name,
                    "matched": best_match.get("name"),
                    "score": best_score,
                },
            )
            return best_match
        else:
            logger.debug(
                "No good match found",
                extra={
                    "company": company_name,
                    "best_score": best_score,
                    "threshold": self.threshold,
                },
            )
            return None

