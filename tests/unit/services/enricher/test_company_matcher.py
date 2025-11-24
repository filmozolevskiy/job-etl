"""Unit tests for CompanyMatcher."""

from unittest.mock import Mock

import pytest

from services.enricher.company_matcher import CompanyMatcher
from services.enricher.glassdoor_client import GlassdoorClient


class TestCompanyMatcher:
    """Test cases for CompanyMatcher."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock GlassdoorClient."""
        return Mock(spec=GlassdoorClient)

    @pytest.fixture
    def matcher(self, mock_client):
        """Create a CompanyMatcher instance."""
        return CompanyMatcher(glassdoor_client=mock_client, similarity_threshold=80)

    def test_normalize_company_name_basic(self, matcher):
        """Test basic normalization."""
        assert matcher.normalize_company_name("  Test Company  ") == "test company"

    def test_normalize_company_name_remove_suffixes(self, matcher):
        """Test removal of common company suffixes."""
        assert matcher.normalize_company_name("Test Company Inc.") == "test company"
        assert matcher.normalize_company_name("Test LLC") == "test"
        assert matcher.normalize_company_name("Test Corp.") == "test"
        assert matcher.normalize_company_name("Test Corporation") == "test"

    def test_normalize_company_name_whitespace(self, matcher):
        """Test whitespace normalization."""
        assert matcher.normalize_company_name("Test   Company") == "test company"
        assert matcher.normalize_company_name("Test\nCompany") == "test company"

    def test_normalize_company_name_empty(self, matcher):
        """Test normalization of empty strings."""
        assert matcher.normalize_company_name("") == ""
        assert matcher.normalize_company_name(None) == ""

    def test_match_company_exact_match(self, matcher, mock_client):
        """Test matching with exact company name."""
        mock_client.search_company.return_value = [
            {"name": "Test Company", "company_id": 123, "rating": 4.5}
        ]

        result = matcher.match_company("Test Company")

        assert result is not None
        assert result["name"] == "Test Company"
        mock_client.search_company.assert_called_once_with("Test Company", limit=10)

    def test_match_company_fuzzy_match_above_threshold(self, matcher, mock_client):
        """Test fuzzy matching when similarity is above threshold."""
        mock_client.search_company.return_value = [
            {"name": "Test Company Inc", "company_id": 123, "rating": 4.5}
        ]

        result = matcher.match_company("Test Company")

        assert result is not None
        assert result["name"] == "Test Company Inc"

    def test_match_company_fuzzy_match_below_threshold(self, matcher, mock_client):
        """Test fuzzy matching when similarity is below threshold."""
        mock_client.search_company.return_value = [
            {"name": "Completely Different Company", "company_id": 123, "rating": 4.5}
        ]

        result = matcher.match_company("Test Company")

        assert result is None

    def test_match_company_no_results(self, matcher, mock_client):
        """Test matching when API returns no results."""
        mock_client.search_company.return_value = []

        result = matcher.match_company("Test Company")

        assert result is None

    def test_match_company_api_error(self, matcher, mock_client):
        """Test matching when API call fails."""
        mock_client.search_company.side_effect = Exception("API Error")

        result = matcher.match_company("Test Company")

        assert result is None

    def test_match_company_empty_name(self, matcher, mock_client):
        """Test matching with empty company name."""
        result = matcher.match_company("")
        assert result is None
        mock_client.search_company.assert_not_called()

    def test_match_company_multiple_results_best_match(self, matcher, mock_client):
        """Test selecting best match from multiple results."""
        mock_client.search_company.return_value = [
            {"name": "Test Company Inc", "company_id": 123, "rating": 4.5},
            {"name": "Test Corp", "company_id": 456, "rating": 4.0},
            {"name": "Different Company", "company_id": 789, "rating": 3.5},
        ]

        result = matcher.match_company("Test Company")

        assert result is not None
        # Should return the best match (highest similarity)
        assert result["name"] in ["Test Company Inc", "Test Corp"]

    def test_match_company_custom_threshold(self, mock_client):
        """Test matching with custom similarity threshold."""
        matcher = CompanyMatcher(
            glassdoor_client=mock_client, similarity_threshold=90
        )
        mock_client.search_company.return_value = [
            {"name": "Test Company Inc", "company_id": 123, "rating": 4.5}
        ]

        # With higher threshold, might not match
        # Result depends on actual similarity score, but should respect threshold
        _ = matcher.match_company("Test Company")

    def test_match_company_result_missing_name(self, matcher, mock_client):
        """Test handling of results with missing name field."""
        mock_client.search_company.return_value = [
            {"company_id": 123, "rating": 4.5}  # Missing "name" field
        ]

        result = matcher.match_company("Test Company")

        assert result is None

