"""
Command-line entry point for the enricher service.

The service extracts skills from job descriptions using spaCy and curated
keyword dictionaries, then writes the normalized skill arrays back to
``staging.job_postings_stg``. Downstream dbt models consume those values
when building marts.fact_jobs.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from typing import Optional

from dotenv import load_dotenv

from .db_operations import DatabaseError, EnricherDB
from .skills_extractor import SkillsDictionary, SkillsExtractor, load_skills_dictionary

# Load environment variables from .env when available.
load_dotenv()


logger = logging.getLogger(__name__)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the enricher service."""
    parser = argparse.ArgumentParser(
        description="Enrich job postings with extracted skills",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of jobs to process in this run",
        default=None,
    )
    parser.add_argument(
        "--source",
        action="append",
        help="Filter to specific source(s). Can be provided multiple times.",
        default=None,
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Reprocess rows that already contain skills.",
    )
    parser.add_argument(
        "--dictionary-path",
        type=str,
        help="Override path to skills_dictionary.yml",
        default=os.getenv("SKILLS_DICTIONARY_PATH"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract skills but do not persist updates.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser.parse_args(argv)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _load_dictionary(path: Optional[str]) -> SkillsDictionary:
    if path:
        logger.info("Loading skills dictionary from %s", path)
    return load_skills_dictionary(path)


def run_enricher(
    *,
    db: EnricherDB,
    extractor: SkillsExtractor,
    limit: Optional[int] = None,
    sources: Optional[Sequence[str]] = None,
    include_existing: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Execute the enrichment workflow.

    Args:
        db: Database access layer.
        extractor: Skills extractor instance.
        limit: Optional maximum number of jobs to process.
        sources: Optional list of source filters.
        include_existing: If True, process rows even if skills already exist.
        dry_run: When True, do not persist database updates.

    Returns:
        Dictionary with counters describing the run.
    """
    stats = {
        "fetched": 0,
        "processed": 0,
        "updated": 0,
        "unchanged": 0,
    }

    jobs = db.fetch_jobs_for_skills(
        sources=sources,
        limit=limit,
        only_missing=not include_existing,
    )
    stats["fetched"] = len(jobs)

    logger.info(
        "Fetched %s job(s) for enrichment (limit=%s, include_existing=%s)",
        stats["fetched"],
        limit,
        include_existing,
    )

    updates: list[tuple[str, list[str]]] = []

    for job in jobs:
        stats["processed"] += 1
        hash_key = job["hash_key"]
        description = job.get("description")
        current_skills = job.get("skills_raw") or []

        new_skills = extractor.extract(description, current_skills)
        current_set = {
            skill.strip().lower()
            for skill in current_skills
            if isinstance(skill, str) and skill.strip()
        }
        new_set = set(new_skills)

        if new_set != current_set:
            logger.debug(
                "Skill update required",
                extra={
                    "hash_key": hash_key,
                    "company": job.get("company"),
                    "job_title": job.get("job_title"),
                    "before": sorted(current_set),
                    "after": sorted(new_set),
                },
            )
            updates.append((hash_key, new_skills))
            stats["updated"] += 1
        else:
            stats["unchanged"] += 1

    if not updates:
        logger.info("No skill updates required")
        return stats

    if dry_run:
        logger.info(
            "Dry run enabled; skipping database update for %s job(s)", len(updates)
        )
        return stats

    updated_rows = db.update_job_skills_batch(updates)
    if updated_rows != len(updates):
        logger.warning(
            "Requested updates for %s job(s) but only %s row(s) were affected",
            len(updates),
            updated_rows,
        )
    else:
        logger.info("Persisted enriched skills for %s job(s)", updated_rows)

    return stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    _configure_logging(args.verbose)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable must be set")
        return 2

    try:
        db = EnricherDB(database_url)
        dictionary = _load_dictionary(args.dictionary_path)
        extractor = SkillsExtractor(dictionary=dictionary)

        stats = run_enricher(
            db=db,
            extractor=extractor,
            limit=args.limit,
            sources=args.source,
            include_existing=args.include_existing,
            dry_run=args.dry_run,
        )

        if stats["updated"] == 0:
            logger.info("Enricher completed; no updates were necessary")
        else:
            logger.info("Enricher completed with %s updates", stats["updated"])
        return 0
    except DatabaseError as exc:
        logger.error("Database error: %s", exc)
        return 2
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())

