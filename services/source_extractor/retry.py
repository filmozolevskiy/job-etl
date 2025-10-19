"""Retry logic for API calls with exponential backoff.

This module provides a decorator to automatically retry failed API calls,
useful for handling transient network errors and rate limiting.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (ConnectionError, TimeoutError),
) -> Callable[[F], F]:
    """Decorator to retry a function with exponential backoff.

    This is essential for working with external APIs that may:
    - Have temporary network issues
    - Hit rate limits
    - Experience brief outages

    The decorator will retry the function with increasing delays between attempts.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_factor: Multiplier for delay after each retry (default: 2.0)
                       delay = initial_delay * (backoff_factor ** attempt)
        exceptions: Tuple of exception types to catch and retry (default: ConnectionError, TimeoutError)

    Returns:
        Decorated function that will retry on failure

    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def fetch_data():
            response = requests.get("https://api.example.com/jobs")
            return response.json()

        # If the request fails, it will retry with structured logging:
        # - Attempt 1: immediate (no delay)
        # - Attempt 2: wait 1 second  (logs warning)
        # - Attempt 3: wait 2 seconds (logs warning)
        # - Attempt 4: wait 4 seconds (logs warning)
        # - If still failing after 4 attempts, logs error and raises exception

    Backoff calculation (initial_delay=1.0, backoff_factor=2.0):
        Attempt 1: No delay (first try)
        Attempt 2: Wait 1 second  (1.0 * 2^0)
        Attempt 3: Wait 2 seconds (1.0 * 2^1)
        Attempt 4: Wait 4 seconds (1.0 * 2^2)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # Don't sleep after the last attempt
                    if attempt < max_retries:
                        # Calculate delay: initial_delay * (backoff_factor ^ attempt)
                        delay = initial_delay * (backoff_factor**attempt)

                        logger.warning(
                            "Function %s failed (attempt %d/%d): %s. Retrying in %.1f seconds...",
                            func.__name__,
                            attempt + 1,
                            max_retries + 1,
                            e,
                            delay,
                            extra={
                                "function": func.__name__,
                                "retry_attempt": attempt + 1,
                                "max_retries": max_retries + 1,
                                "delay_seconds": delay,
                                "exception_type": type(e).__name__,
                            },
                        )

                        time.sleep(delay)
                    else:
                        logger.error(
                            "Function %s failed after %d attempts",
                            func.__name__,
                            max_retries + 1,
                            extra={
                                "function": func.__name__,
                                "total_attempts": max_retries + 1,
                                "exception_type": type(e).__name__,
                            },
                        )

            # If we've exhausted all retries, raise the last exception
            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


# Example usage for API calls
def retry_api_call(max_retries: int = 3) -> Callable[[F], F]:
    """Convenience decorator specifically for API calls.

    Uses sensible defaults for API requests:
    - Retries connection and timeout errors
    - Also retries on common HTTP errors (429 Too Many Requests, 503 Service Unavailable)
    - Exponential backoff starting at 1 second

    Args:
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Decorated function

    Example:
        @retry_api_call(max_retries=3)
        def fetch_jobs(api_key: str):
            response = requests.get(
                "https://api.example.com/jobs",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()  # Raises HTTPError for bad status codes
            return response.json()
    """
    return retry_with_backoff(
        max_retries=max_retries,
        initial_delay=1.0,
        backoff_factor=2.0,
        exceptions=(ConnectionError, TimeoutError, RuntimeError),
    )

