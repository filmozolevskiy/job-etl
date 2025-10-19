"""Source Extractor Service.

This service is responsible for fetching job postings from external APIs
and storing the raw JSON responses for further processing.

Main components:
- SourceAdapter: Abstract base class for all data source adapters
- JobPostingRaw: Data class for raw job postings
- Adapters: Provider-specific implementations (in adapters/ directory)
"""

from .base import JobPostingRaw, SourceAdapter

__all__ = ["SourceAdapter", "JobPostingRaw"]
__version__ = "0.1.0"

