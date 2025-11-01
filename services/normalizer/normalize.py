"""
Job Posting Normalization Logic

This module transforms raw job posting data from various providers into our
canonical format. It handles field mapping, type conversions, default values,
and data validation.

Key Responsibilities:
- Map provider-specific fields to our standard schema
- Apply default values for missing optional fields
- Ensure required fields are present and valid
- Normalize enum values to match our schema constraints
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .hash_generator import generate_hash_key

logger = logging.getLogger(__name__)


# Valid enum values (must match database CHECK constraints)
VALID_REMOTE_TYPES = {'remote', 'hybrid', 'onsite', 'unknown'}
VALID_CONTRACT_TYPES = {'full_time', 'part_time', 'contract', 'intern', 'temp', 'unknown'}
VALID_COMPANY_SIZES = {'1-10', '11-50', '51-200', '201-500', '501-1000', '1001-5000', '5001+', 'unknown'}


class NormalizationError(Exception):
    """Raised when a job posting cannot be normalized due to invalid or missing data."""
    pass


def normalize_job_posting(raw_data: dict[str, Any], source: str) -> dict[str, Any]:
    """
    Normalize a raw job posting into our canonical format.

    This function takes a raw job posting dictionary (from any provider) and
    transforms it into a standardized format that matches the staging table schema.

    The normalized format includes:
    - All required fields with appropriate defaults
    - Validated enum values
    - Generated hash_key for deduplication
    - Timestamps for tracking

    Args:
        raw_data: Dictionary containing raw job posting data
                 Expected to match output of SourceAdapter.map_to_common()
        source: Name of the data source (e.g., "jsearch", "linkedin")

    Returns:
        Dictionary with normalized job posting ready for database insertion:
        {
            'hash_key': str,           # Generated MD5 hash
            'provider_job_id': str | None,
            'job_link': str | None,
            'job_title': str,          # Required
            'company': str,            # Required
            'company_size': str,       # Default: 'unknown'
            'location': str,           # Required
            'remote_type': str,        # Default: 'unknown'
            'contract_type': str,      # Default: 'unknown'
            'salary_min': float | None,
            'salary_max': float | None,
            'salary_currency': str | None,
            'description': str | None,
            'skills_raw': list[str] | None,
            'posted_at': datetime | None,
            'apply_url': str | None,
            'source': str              # Required
        }

    Raises:
        NormalizationError: If required fields are missing or invalid

    Examples:
        >>> raw = {
        ...     'job_title': 'Data Engineer',
        ...     'company': 'Acme Corp',
        ...     'location': 'Montreal, QC',
        ...     'remote_type': 'hybrid',
        ...     'contract_type': 'full_time',
        ...     'source': 'jsearch'
        ... }
        >>> normalized = normalize_job_posting(raw, 'jsearch')
        >>> normalized['hash_key']  # Will be 32-char MD5 hash
        'a1b2c3d4...'
    """
    try:
        # Extract and validate required fields
        job_title = raw_data.get('job_title')
        company = raw_data.get('company')
        location = raw_data.get('location')

        if not job_title or not isinstance(job_title, str):
            raise NormalizationError("job_title is required and must be a non-empty string")

        if not company or not isinstance(company, str):
            raise NormalizationError("company is required and must be a non-empty string")

        if not location or not isinstance(location, str):
            raise NormalizationError("location is required and must be a non-empty string")

        # Generate hash key for deduplication
        try:
            hash_key = generate_hash_key(company, job_title, location)
        except ValueError as e:
            raise NormalizationError(f"Failed to generate hash key: {e}") from e

        # Normalize enum fields with defaults
        remote_type = _normalize_enum(
            raw_data.get('remote_type'),
            VALID_REMOTE_TYPES,
            'unknown',
            'remote_type'
        )

        contract_type = _normalize_enum(
            raw_data.get('contract_type'),
            VALID_CONTRACT_TYPES,
            'unknown',
            'contract_type'
        )

        company_size = _normalize_enum(
            raw_data.get('company_size'),
            VALID_COMPANY_SIZES,
            'unknown',
            'company_size'
        )

        # Parse posted_at timestamp if present
        posted_at = _parse_timestamp(raw_data.get('posted_at'))

        # Parse salary fields
        salary_min = _parse_numeric(raw_data.get('salary_min'), 'salary_min')
        salary_max = _parse_numeric(raw_data.get('salary_max'), 'salary_max')

        # Validate salary logic
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            logger.warning(
                "salary_min > salary_max, swapping values",
                extra={
                    'company': company,
                    'job_title': job_title,
                    'salary_min': salary_min,
                    'salary_max': salary_max,
                }
            )
            salary_min, salary_max = salary_max, salary_min

        # Build normalized job posting
        normalized = {
            'hash_key': hash_key,
            'provider_job_id': _safe_string(raw_data.get('provider_job_id')),
            'job_link': _safe_string(raw_data.get('job_link')),
            'job_title': job_title.strip(),
            'company': company.strip(),
            'company_size': company_size,
            'location': location.strip(),
            'remote_type': remote_type,
            'contract_type': contract_type,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'salary_currency': _safe_string(raw_data.get('salary_currency')),
            'description': _safe_string(raw_data.get('description')),
            'skills_raw': raw_data.get('skills_raw') if isinstance(raw_data.get('skills_raw'), list) else None,
            'posted_at': posted_at,
            'apply_url': _safe_string(raw_data.get('apply_url')),
            'source': source,
        }

        logger.debug(
            "Successfully normalized job posting",
            extra={
                'hash_key': hash_key,
                'company': company,
                'job_title': job_title,
                'source': source,
            }
        )

        return normalized

    except NormalizationError:
        # Re-raise normalization errors as-is
        raise
    except Exception as e:
        # Catch unexpected errors and wrap them
        logger.error(
            "Unexpected error during normalization",
            extra={
                'error': str(e),
                'error_type': type(e).__name__,
                'raw_data_keys': list(raw_data.keys()) if raw_data else None,
            }
        )
        raise NormalizationError(f"Unexpected normalization error: {e}") from e


def _normalize_enum(
    value: Any,
    valid_values: set[str],
    default: str,
    field_name: str
) -> str:
    """
    Normalize an enum field value.

    If the value is valid, return it as-is.
    If invalid or missing, return the default value and log a warning.

    Args:
        value: Raw enum value
        valid_values: Set of acceptable values
        default: Default value to use if invalid
        field_name: Name of field (for logging)

    Returns:
        Validated enum value or default
    """
    if value is None or value == '':
        return default

    if not isinstance(value, str):
        logger.warning(
            f"{field_name} must be string, got {type(value).__name__}, using default",
            extra={'value': value, 'default': default}
        )
        return default

    normalized = value.lower().strip()

    if normalized not in valid_values:
        logger.warning(
            f"Invalid {field_name} value, using default",
            extra={
                'value': value,
                'valid_values': valid_values,
                'default': default
            }
        )
        return default

    return normalized


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """
    Parse a timestamp value into a datetime object.

    Supports:
    - ISO 8601 strings (e.g., "2025-10-15T10:00:00Z")
    - Unix timestamps (seconds since epoch)
    - datetime objects (passed through)
    - None (returns None)

    Args:
        value: Timestamp value to parse

    Returns:
        datetime object or None if invalid/missing
    """
    if value is None:
        return None

    # Already a datetime
    if isinstance(value, datetime):
        return value

    # Try parsing ISO 8601 string
    if isinstance(value, str):
        try:
            # Handle various ISO formats
            # Remove 'Z' suffix and parse
            cleaned = value.replace('Z', '+00:00')
            return datetime.fromisoformat(cleaned)
        except ValueError:
            logger.warning(
                "Failed to parse timestamp string",
                extra={'value': value}
            )
            return None

    # Try parsing Unix timestamp
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError):
            logger.warning(
                "Failed to parse Unix timestamp",
                extra={'value': value}
            )
            return None

    logger.warning(
        "Unsupported timestamp type",
        extra={'value': value, 'type': type(value).__name__}
    )
    return None


def _parse_numeric(value: Any, field_name: str) -> Optional[float]:
    """
    Parse a numeric value safely.

    Args:
        value: Value to parse
        field_name: Name of field (for logging)

    Returns:
        Float value or None if invalid/missing
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            logger.warning(
                f"Failed to parse {field_name} as number",
                extra={'value': value}
            )
            return None

    logger.warning(
        f"Invalid {field_name} type",
        extra={'value': value, 'type': type(value).__name__}
    )
    return None


def _safe_string(value: Any) -> Optional[str]:
    """
    Safely convert a value to string or None.

    Args:
        value: Value to convert

    Returns:
        String value or None if empty/None
    """
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None

    # Convert other types to string
    return str(value)


