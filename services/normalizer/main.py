"""
Normalizer Service - Main Entry Point

This is the command-line interface for the normalizer service.
It can be called directly from the terminal or from Airflow tasks.

Usage:
    python -m services.normalizer.main [OPTIONS]

Options:
    --source TEXT         Filter by source name (e.g., 'jsearch')
    --limit INTEGER       Maximum number of jobs to process
    --min-collected-at    Process only jobs collected after this timestamp
    --dry-run            Print what would be done without writing to database
    --verbose            Enable debug logging
    --help               Show this message and exit

Examples:
    # Process all raw jobs from JSearch:
    python -m services.normalizer.main --source jsearch

    # Process up to 100 jobs with verbose logging:
    python -m services.normalizer.main --limit 100 --verbose

    # Dry run to see what would be processed:
    python -m services.normalizer.main --dry-run

Exit Codes:
    0: Success
    1: Normalization errors occurred (some jobs failed)
    2: Fatal error (database connection, etc.)
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

from .db_operations import DatabaseError, NormalizerDB
from .normalize import NormalizationError, normalize_job_posting

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='Normalize raw job postings into canonical format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--source',
        type=str,
        help='Filter by source name (e.g., "jsearch")',
        default=None
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of jobs to process',
        default=None
    )

    parser.add_argument(
        '--min-collected-at',
        type=str,
        help='Process only jobs collected after this timestamp (ISO format)',
        default=None,
        dest='min_collected_at'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be done without writing to database',
        dest='dry_run'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging'
    )

    return parser.parse_args()


def run_normalizer(
    db: NormalizerDB,
    source: Optional[str] = None,
    limit: Optional[int] = None,
    min_collected_at: Optional[str] = None,
    dry_run: bool = False
) -> dict[str, int]:
    """
    Main normalizer logic.

    Args:
        db: Database interface
        source: Filter by source name
        limit: Maximum number of jobs to process
        min_collected_at: Filter by collection timestamp
        dry_run: If True, don't write to database

    Returns:
        Dictionary with statistics:
        - fetched: Number of raw jobs fetched
        - normalized: Number successfully normalized
        - upserted: Number written to staging
        - failed: Number that failed normalization
        - skipped: Number skipped due to errors
    """
    stats = {
        'fetched': 0,
        'normalized': 0,
        'upserted': 0,
        'failed': 0,
        'skipped': 0,
    }

    start_time = datetime.now(timezone.utc)

    logger.info(
        "Starting normalizer service",
        extra={
            'source': source,
            'limit': limit,
            'min_collected_at': min_collected_at,
            'dry_run': dry_run,
        }
    )

    # Fetch raw jobs from database
    try:
        raw_jobs = db.fetch_raw_jobs(
            source=source,
            limit=limit,
            min_collected_at=min_collected_at
        )
        stats['fetched'] = len(raw_jobs)

        if not raw_jobs:
            logger.warning("No raw jobs found to process")
            return stats

        logger.info(f"Fetched {len(raw_jobs)} raw jobs to process")

    except DatabaseError as e:
        logger.error(f"Failed to fetch raw jobs: {e}")
        raise

    # Import adapters for mapping raw payloads to common format
    from services.source_extractor.adapters.jsearch_adapter import JSearchAdapter
    from services.source_extractor.base import JobPostingRaw

    # Initialize adapters (could be moved to a registry pattern for multiple sources)
    adapters = {
        'jsearch': JSearchAdapter()
    }

    # Process each raw job
    normalized_jobs = []

    for raw_job in raw_jobs:
        try:
            # The payload contains the RAW API response
            raw_payload = raw_job['payload']
            source_name = raw_job['source']

            # Map raw API response to common format
            adapter = adapters.get(source_name)
            if not adapter:
                stats['skipped'] += 1
                logger.warning(
                    f"No adapter found for source: {source_name}",
                    extra={'raw_id': raw_job.get('raw_id')}
                )
                continue

            # Create JobPostingRaw object and map to common format
            job_raw = JobPostingRaw(
                source=source_name,
                payload=raw_payload,
                provider_job_id=raw_payload.get('job_id')
            )
            common_format = adapter.map_to_common(job_raw)

            # Normalize the common format (validate, add hash, apply defaults)
            normalized = normalize_job_posting(common_format, source_name)
            normalized_jobs.append(normalized)
            stats['normalized'] += 1

            logger.debug(
                "Normalized job posting",
                extra={
                    'hash_key': normalized['hash_key'],
                    'company': normalized['company'],
                    'job_title': normalized['job_title'],
                }
            )

        except NormalizationError as e:
            stats['failed'] += 1
            logger.warning(
                "Failed to normalize job posting",
                extra={
                    'raw_id': raw_job.get('raw_id'),
                    'source': raw_job.get('source'),
                    'error': str(e),
                }
            )
            # Continue processing other jobs

        except Exception as e:
            stats['skipped'] += 1
            logger.error(
                "Unexpected error normalizing job",
                extra={
                    'raw_id': raw_job.get('raw_id'),
                    'source': raw_job.get('source'),
                    'error': str(e),
                    'error_type': type(e).__name__,
                }
            )
            # Continue processing other jobs

    # Write to staging table (unless dry run)
    if not dry_run and normalized_jobs:
        try:
            logger.info(f"Upserting {len(normalized_jobs)} normalized jobs to staging")
            upserted_count = db.upsert_staging_jobs_batch(normalized_jobs)
            stats['upserted'] = upserted_count

            logger.info(
                f"Successfully upserted {upserted_count} jobs to staging"
            )

        except DatabaseError as e:
            logger.error(f"Failed to upsert jobs to staging: {e}")
            raise
    elif dry_run:
        logger.info(
            f"DRY RUN: Would upsert {len(normalized_jobs)} jobs to staging"
        )
        stats['upserted'] = 0

    # Log final statistics
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    logger.info(
        "Normalizer service completed",
        extra={
            'duration_seconds': duration,
            'fetched': stats['fetched'],
            'normalized': stats['normalized'],
            'upserted': stats['upserted'],
            'failed': stats['failed'],
            'skipped': stats['skipped'],
        }
    )

    return stats


def main() -> int:
    """
    Main entry point for the normalizer service.

    Returns:
        Exit code (0 = success, 1 = partial failure, 2 = fatal error)
    """
    args = parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Get database connection string from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable must be set")
        return 2  # Fatal error - cannot proceed without database

    try:
        # Initialize database connection
        logger.info("Connecting to database")
        db = NormalizerDB(database_url)

        # Run normalizer
        stats = run_normalizer(
            db=db,
            source=args.source,
            limit=args.limit,
            min_collected_at=args.min_collected_at,
            dry_run=args.dry_run
        )

        # Determine exit code based on results
        if stats['failed'] > 0 or stats['skipped'] > 0:
            logger.warning(
                f"Completed with errors: {stats['failed']} failed, {stats['skipped']} skipped"
            )
            return 1  # Partial failure

        if stats['normalized'] == 0:
            logger.warning("No jobs were normalized")
            return 0  # Success but nothing to do

        logger.info("Normalizer completed successfully")
        return 0  # Success

    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        return 2  # Fatal error

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130  # Standard Unix exit code for SIGINT

    except Exception as e:
        logger.error(
            "Unexpected fatal error",
            extra={
                'error': str(e),
                'error_type': type(e).__name__,
            },
            exc_info=True
        )
        return 2  # Fatal error


if __name__ == '__main__':
    sys.exit(main())


