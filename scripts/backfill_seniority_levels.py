"""
Deprecated: seniority backfill is now owned by the enricher service.

This script previously:
1. Read job postings from staging.job_postings_stg where seniority_level = 'unknown'
2. Re-extracted seniority level from job_title
3. Wrote updated seniority levels back to the database

The pipeline has been refactored so that:
- Seniority is computed by the `enricher` service and persisted via
  `seniority_level` and `seniority_enrichment_status`.
- The ranker consumes the stored `seniority_level` directly.

To recompute seniority, run the enricher task/DAG instead of this script.

This module is kept only as a stub for historical reference and will no longer
perform any database operations.
"""

from __future__ import annotations

import sys
from typing import Final

DEPRECATION_MESSAGE: Final[str] = (
    "scripts/backfill_seniority_levels.py is deprecated.\n"
    "Seniority enrichment is now handled by the enricher service via the "
    "`seniority_enrichment_status` workflow.\n"
    "Please trigger the enricher (or the full Airflow DAG) to recompute "
    "seniority levels instead of using this script."
)


def main() -> int:
    """Entry point that only reports deprecation."""
    print(DEPRECATION_MESSAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
