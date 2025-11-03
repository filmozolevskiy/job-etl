"""
Ranker Service - Main Entry Point

This is the command-line interface for the ranker service.
It can be called directly from the terminal or from Airflow tasks.

Usage:
    python -m services.ranker.main [OPTIONS]

Options:
    --config TEXT         Path to ranking.yml configuration file
    --limit INTEGER       Maximum number of jobs to rank
    --all                 Rank all jobs, including already ranked ones
    --dry-run            Print what would be done without writing to database
    --verbose            Enable debug logging
    --help               Show this message and exit

Examples:
    # Rank all unranked jobs:
    python -m services.ranker.main

    # Rank up to 100 jobs with verbose logging:
    python -m services.ranker.main --limit 100 --verbose

    # Dry run to see what would be ranked:
    python -m services.ranker.main --dry-run

Exit Codes:
    0: Success
    1: Ranking errors occurred (some jobs failed)
    2: Fatal error (database connection, config loading, etc.)
"""

import argparse
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv

from .config_loader import RankingConfig, load_ranking_config
from .db_operations import DatabaseError, RankerDB
from .scoring import calculate_rank

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
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Rank job postings based on configurable weights and profile preferences',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to ranking.yml configuration file (default: config/ranking.yml)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of jobs to rank (default: no limit)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Rank all jobs, including already ranked ones (re-rank existing scores)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be done without writing to database'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable debug logging'
    )

    return parser.parse_args()


def run_ranker(
    db: RankerDB,
    config: RankingConfig,
    limit: Optional[int] = None,
    re_rank_all: bool = False,
    dry_run: bool = False
) -> dict[str, int]:
    """
    Main ranker logic.

    Args:
        db: Database interface
        config: Ranking configuration
        limit: Maximum number of jobs to process
        re_rank_all: If True, rank all jobs including already ranked ones
        dry_run: If True, don't write to database

    Returns:
        Dictionary with statistics:
        - fetched: Number of jobs fetched
        - ranked: Number successfully ranked
        - failed: Number that failed ranking
    """
    stats = {
        'fetched': 0,
        'ranked': 0,
        'failed': 0,
    }

    logger.info(
        "Starting ranker service",
        extra={
            'limit': limit,
            're_rank_all': re_rank_all,
            'dry_run': dry_run,
        }
    )

    # Fetch jobs from database
    try:
        jobs = db.fetch_unranked_jobs(
            limit=limit,
            where_rank_score_is_null=not re_rank_all
        )
        stats['fetched'] = len(jobs)

        if not jobs:
            logger.warning("No jobs found to rank")
            return stats

        logger.info(f"Fetched {len(jobs)} jobs to rank")

    except DatabaseError as e:
        logger.error(f"Failed to fetch jobs: {e}")
        raise

    # Rank each job
    rankings = []
    for i, job in enumerate(jobs, 1):
        try:
            logger.debug(
                f"Ranking job {i}/{len(jobs)}",
                extra={'hash_key': job.get('hash_key')}
            )

            rank_score, rank_explain = calculate_rank(job, config)

            rankings.append({
                'hash_key': job['hash_key'],
                'rank_score': rank_score,
                'rank_explain': rank_explain,
            })

            stats['ranked'] += 1

            logger.debug(
                f"Job ranked: score={rank_score:.2f}",
                extra={
                    'hash_key': job.get('hash_key'),
                    'rank_score': rank_score,
                }
            )

        except Exception as e:
            stats['failed'] += 1
            logger.warning(
                f"Failed to rank job",
                extra={
                    'error': str(e),
                    'hash_key': job.get('hash_key'),
                }
            )
            # Continue processing other jobs

    # Update database (unless dry run)
    if rankings and not dry_run:
        try:
            updated_count = db.update_jobs_ranking_batch(rankings)
            logger.info(
                f"Updated {updated_count} job rankings in database",
                extra={'jobs_updated': updated_count}
            )
        except DatabaseError as e:
            logger.error(f"Failed to update rankings: {e}")
            raise
    elif rankings and dry_run:
        logger.info(f"DRY RUN: Would update {len(rankings)} job rankings")

    logger.info(
        "Ranker service completed",
        extra={
            'stats': stats,
        }
    )

    return stats


def main() -> int:
    """
    Main entry point for the ranker service.

    Returns:
        Exit code (0 = success, 1 = some failures, 2 = fatal error)
    """
    args = parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    try:
        # Load configuration
        logger.info("Loading ranking configuration")
        config = load_ranking_config(args.config)

        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable must be set. "
                "Expected format: postgresql://user:password@host:port/dbname"
            )

        logger.info("Connecting to database")
        db = RankerDB(database_url)

        # Run ranker
        stats = run_ranker(
            db=db,
            config=config,
            limit=args.limit,
            re_rank_all=args.all,
            dry_run=args.dry_run
        )

        # Print summary
        print("\n" + "=" * 60)
        print("RANKER SUMMARY")
        print("=" * 60)
        print(f"Fetched:  {stats['fetched']}")
        print(f"Ranked:   {stats['ranked']}")
        print(f"Failed:   {stats['failed']}")
        print("=" * 60)

        # Show overall stats
        if not args.dry_run:
            overall_stats = db.get_ranking_stats()
            print(f"\nOverall Statistics:")
            print(f"  Total jobs:     {overall_stats['total_jobs']}")
            print(f"  Ranked jobs:    {overall_stats['ranked_jobs']}")
            print(f"  Unranked jobs:  {overall_stats['unranked_jobs']}")
            if overall_stats['average_score']:
                print(f"  Average score:  {overall_stats['average_score']:.2f}")
                print(f"  Top score:      {overall_stats['top_score']:.2f}")
                print(f"  Bottom score:   {overall_stats['bottom_score']:.2f}")

        # Return exit code based on results
        if stats['failed'] > 0:
            return 1  # Some failures occurred
        return 0  # Success

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130  # Standard exit code for Ctrl+C
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        return 2


if __name__ == '__main__':
    sys.exit(main())


