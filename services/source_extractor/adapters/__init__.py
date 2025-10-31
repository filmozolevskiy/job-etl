"""Job API Adapters.

This package contains concrete implementations of the SourceAdapter interface
for different job posting APIs.

Available adapters:
- MockAdapter: For testing purposes (mock_adapter.py)
- JSearchAdapter: JSearch API integration (jsearch_adapter.py)
"""

from .mock_adapter import MockAdapter
from .jsearch_adapter import JSearchAdapter

__all__ = ["MockAdapter", "JSearchAdapter"]
__version__ = "0.1.0"
