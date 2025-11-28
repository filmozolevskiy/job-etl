"""
Backfill script to rank all unranked jobs.

This script:
1. Fetches all unranked jobs from marts.fact_jobs (ignoring date filters)
2. Calculates rank scores for each job
3. Updates the database with rankings

Usage:
    python scripts/backfill_rankings.py [--limit N] [--dry-run] [--verbose]

Options:
    --limit N       Maximum number of jobs to rank (default: no limit)
    --dry-run       Print what would be done without writing to database
    --verbose       Enable debug logging

Example:
    # Backfill all unranked jobs
    python scripts/backfill_rankings.py

    # Backfill up to 100 jobs with verbose logging
    python scripts/backfill_rankings.py --limit 100 --verbose

    # Dry run to see what would be ranked
    python scripts/backfill_rankings.py --dry-run
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import after path modification
from services.ranker.config_loader import load_ranking_config  # noqa: E402
from services.ranker.db_operations import DatabaseError, RankerDB  # noqa: E402
from services.ranker.scoring import calculate_rank  # noqa: E402

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill script to rank all unranked jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of jobs to rank (default: no limit)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to database",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the backfill script.

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
        config = load_ranking_config()

        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable must be set. "
                "Expected format: postgresql://user:password@host:port/dbname"
            )

        logger.info("Connecting to database")
        db = RankerDB(database_url)

        # Get stats before backfill
        stats_before = db.get_ranking_stats()
        logger.info(
            f"Current stats: {stats_before['ranked_jobs']} ranked, "
            f"{stats_before['unranked_jobs']} unranked out of {stats_before['total_jobs']} total"
        )

        # Fetch ALL unranked jobs (no date filter for backfill)
        logger.info("Fetching all unranked jobs (ignoring date filters for backfill)")
        jobs = db.fetch_unranked_jobs(
            limit=args.limit,
            where_rank_score_is_null=True,
            min_ingested_at=None,  # No date filter - get all unranked jobs
        )

        if not jobs:
            logger.info("No unranked jobs found to backfill")
            return 0

        logger.info(f"Found {len(jobs)} unranked jobs to rank")

        # Rank each job
        rankings = []
        failed_count = 0

        for i, job in enumerate(jobs, 1):
            try:
                if i % 10 == 0 or i == len(jobs):
                    logger.info(f"Ranking job {i}/{len(jobs)}...")

                rank_score, rank_explain = calculate_rank(job, config)

                rankings.append(
                    {
                        "hash_key": job["hash_key"],
                        "rank_score": rank_score,
                        "rank_explain": rank_explain,
                    }
                )

                logger.debug(
                    f"Job ranked: score={rank_score:.2f}",
                    extra={
                        "hash_key": job.get("hash_key"),
                        "rank_score": rank_score,
                    },
                )

            except Exception as e:
                failed_count += 1
                logger.warning(
                    "Failed to rank job",
                    extra={
                        "error": str(e),
                        "hash_key": job.get("hash_key"),
                    },
                )
                # Continue processing other jobs

        # Update database (unless dry run)
        if rankings and not args.dry_run:
            logger.info(f"Updating database with {len(rankings)} rankings...")
            updated_count = db.update_jobs_ranking_batch(rankings)
            logger.info(f"Successfully updated {updated_count} job rankings")
        elif rankings and args.dry_run:
            logger.info(f"DRY RUN: Would update {len(rankings)} job rankings")
            updated_count = 0
        else:
            updated_count = 0

        # Get stats after backfill
        if not args.dry_run:
            stats_after = db.get_ranking_stats()

        # Print summary
        print("\n" + "=" * 60)
        print("BACKFILL SUMMARY")
        print("=" * 60)
        print(f"Jobs found:    {len(jobs)}")
        print(f"Successfully ranked: {len(rankings)}")
        print(f"Failed:        {failed_count}")
        if not args.dry_run:
            print(f"Updated in DB: {updated_count}")
            print(
                f"\nBefore: {stats_before['ranked_jobs']} ranked, {stats_before['unranked_jobs']} unranked"
            )
            print(
                f"After:  {stats_after['ranked_jobs']} ranked, {stats_after['unranked_jobs']} unranked"
            )
        else:
            print("\nDRY RUN - No database updates made")
        print("=" * 60)

        # Determine exit code
        if failed_count > 0:
            logger.warning(f"Completed with {failed_count} failures")
            return 1

        logger.info("Backfill completed successfully")
        return 0

    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        return 2

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 2

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130

    except Exception as e:
        logger.error(
            "Unexpected fatal error",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
