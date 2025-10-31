"""
Normalizer Service

This service transforms raw job posting JSON from various providers into a
canonical format that can be used by downstream services.

Key responsibilities:
- Read raw JSON from raw.job_postings_raw table
- Transform provider-specific fields to our standard schema
- Generate hash_key for deduplication
- Write normalized data to staging.job_postings_stg using upsert logic
"""

__version__ = "0.1.0"

