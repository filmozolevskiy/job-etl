"""Tests for retry logic with exponential backoff."""

import time

import pytest

from services.source_extractor.retry import retry_api_call, retry_with_backoff


class TestRetryLogic:
    """Tests for the retry decorator."""

    def test_retry_succeeds_on_first_attempt(self):
        """Function that succeeds immediately should not retry."""
        call_count = {"count": 0}

        @retry_with_backoff(max_retries=3)
        def successful_function():
            call_count["count"] += 1
            return "success"

        result = successful_function()
        assert result == "success"
        assert call_count["count"] == 1

    def test_retry_succeeds_after_failures(self):
        """Function should retry until it succeeds."""
        call_count = {"count": 0}

        @retry_with_backoff(max_retries=3, initial_delay=0.1, backoff_factor=2.0)
        def fails_twice_then_succeeds():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = fails_twice_then_succeeds()
        assert result == "success"
        assert call_count["count"] == 3

    def test_retry_exhausts_all_attempts(self):
        """Function should retry max_retries times then raise exception."""
        call_count = {"count": 0}

        @retry_with_backoff(max_retries=3, initial_delay=0.05)
        def always_fails():
            call_count["count"] += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError, match="Always fails"):
            always_fails()

        # Should try initial + 3 retries = 4 total attempts
        assert call_count["count"] == 4

    def test_retry_exponential_backoff_timing(self):
        """Verify exponential backoff delays are correct."""
        call_times = []

        @retry_with_backoff(max_retries=3, initial_delay=0.1, backoff_factor=2.0)
        def fails_always():
            call_times.append(time.time())
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            fails_always()

        # Check that delays increase exponentially
        # Delays should be approximately: 0.1, 0.2, 0.4 seconds
        delays = [
            call_times[i + 1] - call_times[i] for i in range(len(call_times) - 1)
        ]

        # Allow 20% tolerance for timing variations
        assert len(delays) == 3
        assert delays[0] == pytest.approx(0.1, rel=0.2)
        assert delays[1] == pytest.approx(0.2, rel=0.2)
        assert delays[2] == pytest.approx(0.4, rel=0.2)

    def test_retry_only_catches_specified_exceptions(self):
        """Retry should only catch exceptions in the exceptions tuple."""

        @retry_with_backoff(max_retries=2, exceptions=(ConnectionError,))
        def raises_value_error():
            raise ValueError("Wrong exception type")

        # ValueError not in exceptions tuple, should not retry
        with pytest.raises(ValueError, match="Wrong exception type"):
            raises_value_error()

    def test_retry_with_different_exception_types(self):
        """Verify retry works with multiple exception types."""
        call_count = {"count": 0}

        @retry_with_backoff(
            max_retries=3,
            initial_delay=0.05,
            exceptions=(ConnectionError, TimeoutError),
        )
        def fails_with_different_errors():
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise ConnectionError("Connection failed")
            elif call_count["count"] == 2:
                raise TimeoutError("Timeout")
            return "success"

        result = fails_with_different_errors()
        assert result == "success"
        assert call_count["count"] == 3

    def test_retry_api_call_convenience_decorator(self):
        """Test the convenience decorator for API calls."""
        call_count = {"count": 0}

        @retry_api_call(max_retries=2)
        def api_call():
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise ConnectionError("API temporarily down")
            return {"data": "success"}

        result = api_call()
        assert result == {"data": "success"}
        assert call_count["count"] == 2

    def test_retry_preserves_function_metadata(self):
        """Decorator should preserve function name and docstring."""

        @retry_with_backoff(max_retries=1)
        def my_function():
            """This is my function."""
            return "result"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function."

    def test_retry_with_function_arguments(self):
        """Retry should work with functions that take arguments."""
        call_count = {"count": 0}

        @retry_with_backoff(max_retries=2, initial_delay=0.05)
        def function_with_args(x, y, z=3):
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise ConnectionError("Fail")
            return x + y + z

        result = function_with_args(1, 2, z=4)
        assert result == 7
        assert call_count["count"] == 2

    def test_retry_with_no_retries(self):
        """max_retries=0 means try once, no retries."""
        call_count = {"count": 0}

        @retry_with_backoff(max_retries=0)
        def fails_once():
            call_count["count"] += 1
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            fails_once()

        assert call_count["count"] == 1


class TestRetryIntegrationWithAdapter:
    """Test retry logic with the MockAdapter."""

    def test_adapter_with_retry_recovers_from_failure(self):
        """MockAdapter with retry should recover from simulated failures."""
        from services.source_extractor.adapters.mock_adapter import MockAdapter
        from services.source_extractor.retry import retry_api_call

        adapter = MockAdapter(num_jobs=10, fail_on_attempt=1)

        # Wrap fetch with retry decorator
        original_fetch = adapter.fetch
        adapter.fetch = retry_api_call(max_retries=3)(original_fetch)

        # First attempt fails, but should retry and succeed
        jobs, next_token = adapter.fetch()

        assert len(jobs) > 0
        # Note: attempt_count will be 2+ because of retries

# ============================================================================
# Mark all tests as unit tests
# ============================================================================

pytestmark = pytest.mark.unit
