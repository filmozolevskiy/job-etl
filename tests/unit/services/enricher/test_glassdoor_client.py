"""Unit tests for GlassdoorClient."""

from unittest.mock import Mock, patch

import pytest
import requests

from services.enricher.glassdoor_client import GlassdoorClient


class TestGlassdoorClient:
    """Test cases for GlassdoorClient."""

    def test_init_with_api_key(self):
        """Test initialization with API key parameter."""
        client = GlassdoorClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.openwebninja.com"

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization with environment variable."""
        monkeypatch.setenv("GLASSDOOR_API_KEY", "env-key")
        client = GlassdoorClient()
        assert client.api_key == "env-key"

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        client = GlassdoorClient(api_key="test-key", base_url="https://custom.api.com")
        assert client.base_url == "https://custom.api.com"

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="GLASSDOOR_API_KEY must be set"):
            GlassdoorClient(api_key=None)

    @patch("services.enricher.glassdoor_client.requests.get")
    def test_search_company_success(self, mock_get):
        """Test successful company search."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": {
                "status": "OK",
                "data": [
                    {
                        "company_id": 123,
                        "name": "Test Company",
                        "rating": 4.5,
                    }
                ],
            }
        }
        mock_get.return_value = mock_response

        client = GlassdoorClient(api_key="test-key")
        results = client.search_company("Test Company")

        assert len(results) == 1
        assert results[0]["name"] == "Test Company"
        assert results[0]["company_id"] == 123

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "x-api-key" in call_args[1]["headers"]
        assert call_args[1]["headers"]["x-api-key"] == "test-key"
        assert call_args[1]["params"]["query"] == "Test Company"

    @patch("services.enricher.glassdoor_client.requests.get")
    def test_search_company_401_error(self, mock_get):
        """Test handling of 401 Unauthorized error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        client = GlassdoorClient(api_key="test-key")
        with pytest.raises(requests.exceptions.HTTPError, match="Invalid API key"):
            client.search_company("Test Company")

    @patch("services.enricher.glassdoor_client.requests.get")
    def test_search_company_429_error(self, mock_get):
        """Test handling of 429 Rate Limit error."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_get.return_value = mock_response

        client = GlassdoorClient(api_key="test-key")
        with pytest.raises(requests.exceptions.HTTPError, match="Rate limit exceeded"):
            client.search_company("Test Company")

    @patch("services.enricher.glassdoor_client.requests.get")
    def test_search_company_500_error(self, mock_get):
        """Test handling of 500 Server Error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        client = GlassdoorClient(api_key="test-key")
        with pytest.raises(requests.exceptions.HTTPError, match="API error 500"):
            client.search_company("Test Company")

    @patch("services.enricher.glassdoor_client.requests.get")
    def test_search_company_request_exception(self, mock_get):
        """Test handling of network/request exceptions."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        client = GlassdoorClient(api_key="test-key")
        # Per requirement 4c: should return empty list, not raise
        results = client.search_company("Test Company")
        assert results == []

    @patch("services.enricher.glassdoor_client.requests.get")
    def test_search_company_unexpected_response_structure(self, mock_get):
        """Test handling of unexpected response structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "structure"}
        mock_get.return_value = mock_response

        client = GlassdoorClient(api_key="test-key")
        results = client.search_company("Test Company")
        assert results == []

    @patch("services.enricher.glassdoor_client.requests.get")
    def test_search_company_limit_clamping(self, mock_get):
        """Test that limit is clamped between 1 and 100."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": {"status": "OK", "data": []}}
        mock_get.return_value = mock_response

        client = GlassdoorClient(api_key="test-key")

        # Test limit too high
        client.search_company("Test", limit=200)
        call_args = mock_get.call_args
        assert call_args[1]["params"]["limit"] == 100

        # Test limit too low
        client.search_company("Test", limit=0)
        call_args = mock_get.call_args
        assert call_args[1]["params"]["limit"] == 1

