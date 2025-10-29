"""
Hash Key Generator for Job Deduplication

This module provides a pure function to generate unique hash keys for job postings
based on the combination of company name, job title, and location.

The hash key is used as the primary key in the staging table to ensure we don't
store duplicate job postings. Two jobs are considered the same if they have the
same company, title, and location (after normalization).

Key Concepts:
- Whitespace normalization: "Data  Engineer" → "Data Engineer"
- Case folding: "ACME Corp" → "acme corp"
- Deterministic: Same inputs always produce same hash
- MD5 hash: Fixed-length, efficient for indexing
"""

import hashlib
import re


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in a string.
    
    This function:
    1. Removes leading/trailing whitespace
    2. Collapses multiple spaces into a single space
    3. Handles None values safely
    
    Examples:
        >>> normalize_whitespace("  Data   Engineer  ")
        'Data Engineer'
        >>> normalize_whitespace("ACME\\n\\tCorp")
        'ACME Corp'
    
    Args:
        text: Input string to normalize
        
    Returns:
        Normalized string with single spaces, or empty string if input is None
    """
    if not text:
        return ""
    
    # Replace all whitespace characters (spaces, tabs, newlines) with single space
    # Then strip leading/trailing whitespace
    normalized = re.sub(r'\s+', ' ', text.strip())
    
    return normalized


def generate_hash_key(company: str, job_title: str, location: str) -> str:
    """
    Generate a unique hash key for a job posting.
    
    The hash key is used for deduplication. Two jobs with the same company,
    title, and location (after normalization) will have the same hash key.
    
    Algorithm:
    1. Normalize whitespace in each field
    2. Convert to lowercase for case-insensitive comparison
    3. Concatenate with '|' delimiter
    4. Generate MD5 hash
    5. Return hex-encoded hash
    
    Examples:
        >>> generate_hash_key("Acme Corp", "Data Engineer", "Montreal, QC")
        'a1b2c3d4e5f6...'  # 32-character hex string
        
        >>> # These produce the same hash (case and whitespace differences):
        >>> hash1 = generate_hash_key("ACME  CORP", "Data Engineer", "Montreal, QC")
        >>> hash2 = generate_hash_key("acme corp", "data engineer", "Montreal, QC")
        >>> hash1 == hash2
        True
    
    Args:
        company: Company name (e.g., "Acme Corp")
        job_title: Job title (e.g., "Data Engineer")
        location: Location string (e.g., "Montreal, QC, Canada")
        
    Returns:
        32-character hexadecimal MD5 hash string
        
    Raises:
        ValueError: If any required field is None or empty after normalization
    """
    # Normalize and lowercase each component
    company_norm = normalize_whitespace(company).lower()
    title_norm = normalize_whitespace(job_title).lower()
    location_norm = normalize_whitespace(location).lower()
    
    # Validate that all fields are present
    if not company_norm:
        raise ValueError("Company name cannot be empty")
    if not title_norm:
        raise ValueError("Job title cannot be empty")
    if not location_norm:
        raise ValueError("Location cannot be empty")
    
    # Create the composite key with pipe delimiter
    composite_key = f"{company_norm}|{title_norm}|{location_norm}"
    
    # Generate MD5 hash (fast and sufficient for deduplication)
    hash_object = hashlib.md5(composite_key.encode('utf-8'))
    hash_hex = hash_object.hexdigest()
    
    return hash_hex


def validate_hash_key(hash_key: str) -> bool:
    """
    Validate that a string is a valid MD5 hash key.
    
    A valid hash key must be:
    - Exactly 32 characters long
    - Contain only hexadecimal characters (0-9, a-f)
    
    Args:
        hash_key: String to validate
        
    Returns:
        True if valid MD5 hash, False otherwise
        
    Examples:
        >>> validate_hash_key("a1b2c3d4e5f6789012345678901234ab")
        True
        >>> validate_hash_key("invalid")
        False
        >>> validate_hash_key("G1B2C3D4E5F6789012345678901234AB")  # Contains 'G'
        False
    """
    if not hash_key or not isinstance(hash_key, str):
        return False
    
    # MD5 hash is always 32 hexadecimal characters
    if len(hash_key) != 32:
        return False
    
    # Check if all characters are valid hex
    try:
        int(hash_key, 16)
        return True
    except ValueError:
        return False

