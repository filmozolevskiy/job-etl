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

from services.common.seniority_extractor import extract_seniority_level

from .company_matcher import CompanyMatcher
from .db_operations import DatabaseError, EnricherDB
from .glassdoor_client import GlassdoorClient
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
    parser.add_argument(
        "--enrich-companies",
        action="store_true",
        default=True,
        help="Enrich companies with Glassdoor API data (default: True).",
    )
    parser.add_argument(
        "--no-enrich-companies",
        dest="enrich_companies",
        action="store_false",
        help="Disable company enrichment.",
    )
    parser.add_argument(
        "--glassdoor-api-key",
        type=str,
        help="Glassdoor API key (defaults to GLASSDOOR_API_KEY env var).",
        default=None,
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
    enrich_companies: bool = True,
    matcher: Optional[CompanyMatcher] = None,
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

    Args:
        db: Database access layer.
        extractor: Skills extractor instance.
        limit: Optional maximum number of jobs to process.
        sources: Optional list of source filters.
        include_existing: If True, process rows even if skills already exist.
        dry_run: When True, do not persist database updates.
        enrich_companies: If True, run company enrichment after skills extraction.
        matcher: Optional CompanyMatcher instance for company enrichment.

    Returns:
        Dictionary with counters describing the run.
    """
    stats = {
        "skills_jobs_fetched": 0,
        "skills_jobs_processed": 0,
        "skills_jobs_updated": 0,
        "skills_jobs_unchanged": 0,
        "companies_fetched": 0,
        "companies_enriched": 0,
        "companies_skipped": 0,
        "companies_errors": 0,
        "seniority_fetched": 0,
        "seniority_upgraded": 0,
        "seniority_failed": 0,
    }

    # ============================================================
    # STEP 1: Skills Extraction
    # ============================================================
    logger.info("=" * 60)
    logger.info("STEP 1: Skills Extraction")
    logger.info("=" * 60)

    jobs = db.fetch_jobs_for_skills(
        sources=sources,
        limit=limit,
        only_missing=not include_existing,
    )
    stats["skills_jobs_fetched"] = len(jobs)

    logger.info(
        "Fetched %s job(s) for skills extraction (limit=%s, include_existing=%s)",
        stats["skills_jobs_fetched"],
        limit,
        include_existing,
    )

    if not jobs:
        logger.info("No jobs found requiring skills extraction")
    else:
        updates: list[tuple[str, list[str]]] = []

        for job in jobs:
            stats["skills_jobs_processed"] += 1
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
                logger.info(
                    "Skills updated for job: %s (ID: %s); extracted %s skill(s)",
                    job.get("job_title", "Unknown"),
                    hash_key,
                    len(new_set),
                )
                updates.append((hash_key, new_skills))
                stats["skills_jobs_updated"] += 1
            else:
                stats["skills_jobs_unchanged"] += 1

        if updates and not dry_run:
            updated_rows = db.update_job_skills_batch(updates)
            if updated_rows != len(updates):
                logger.warning(
                    "Requested updates for %s job(s) but only %s row(s) were affected",
                    len(updates),
                    updated_rows,
                )
            else:
                logger.info("Persisted enriched skills for %s job(s)", updated_rows)

        if not updates:
            logger.info("No skill updates required")

        if dry_run:
            logger.info(
                "Dry run enabled; skipping database update for %s job(s)", len(updates)
            )

    # Step 1 Summary
    logger.info("-" * 60)
    logger.info(
        "Skills Extraction Summary: jobs_fetched=%s, jobs_processed=%s, "
        "jobs_updated=%s, jobs_unchanged=%s",
        stats["skills_jobs_fetched"],
        stats["skills_jobs_processed"],
        stats["skills_jobs_updated"],
        stats["skills_jobs_unchanged"],
    )
    logger.info("=" * 60)

    # ============================================================
    # STEP 2: Company Enrichment
    # ============================================================
    if enrich_companies and matcher:
        logger.info("=" * 60)
        logger.info("STEP 2: Company Enrichment")
        logger.info("=" * 60)

        company_stats = run_company_enrichment(
            db=db,
            matcher=matcher,
            limit=None,  # Process all companies
        )
        stats["companies_fetched"] = company_stats["fetched"]
        stats["companies_enriched"] = company_stats["enriched"]
        stats["companies_skipped"] = company_stats["skipped"]
        stats["companies_errors"] = company_stats["errors"]
        stats["base_records_created"] = company_stats.get("base_records_created", 0)
    else:
        logger.info("=" * 60)
        logger.info("STEP 2: Company Enrichment - SKIPPED")
        logger.info("=" * 60)

    # ============================================================
    # STEP 3: Seniority Enrichment
    # ============================================================
    logger.info("=" * 60)
    logger.info("STEP 3: Seniority Enrichment")
    logger.info("=" * 60)
    seniority_jobs = db.fetch_jobs_for_seniority(
        sources=sources,
        limit=limit,
    )
    stats["seniority_fetched"] = len(seniority_jobs)

    if not seniority_jobs:
        logger.info("No jobs found requiring seniority enrichment")
        logger.info("-" * 60)
        logger.info(
            "Seniority Enrichment Summary: fetched=0, upgraded=0, failed=0"
        )
        logger.info("=" * 60)
        return stats

    logger.info(
        "Found %s job(s) in staging.job_postings_stg needing seniority enrichment",
        stats["seniority_fetched"],
    )

    seniority_updates: list[tuple[str, Optional[str], str]] = []

    for job in seniority_jobs:
        hash_key = job["hash_key"]
        job_title = job.get("job_title") or ""
        current_level = job.get("seniority_level") or "unknown"

        try:
            new_level = extract_seniority_level(job_title)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "Failed to extract seniority_level for job %s (ID: %s): %s",
                job_title,
                hash_key,
                exc,
            )
            seniority_updates.append((hash_key, current_level, "failed_to_upgrade"))
            stats["seniority_failed"] += 1
            continue

        if new_level != "unknown" and new_level != current_level:
            logger.info(
                "Seniority level upgraded for job: %s (ID: %s); %s -> %s",
                job_title,
                hash_key,
                current_level,
                new_level,
            )
            seniority_updates.append((hash_key, new_level, "upgraded"))
            stats["seniority_upgraded"] += 1
        else:
            # We attempted enrichment but could not improve the level; avoid
            # retrying indefinitely by marking as failed_to_upgrade.
            logger.info(
                "No seniority level upgrade possible for job: %s (ID: %s); "
                "current=%s, detected=%s; marking as failed_to_upgrade",
                job_title,
                hash_key,
                current_level,
                new_level,
            )
            seniority_updates.append((hash_key, current_level, "failed_to_upgrade"))
            stats["seniority_failed"] += 1

    if not seniority_updates:
        logger.info("No seniority updates required")
        logger.info("-" * 60)
        logger.info(
            "Seniority Enrichment Summary: fetched=%s, upgraded=0, failed=0",
            stats["seniority_fetched"],
        )
        logger.info("=" * 60)
        return stats

    if dry_run:
        logger.info(
            "Dry run enabled; skipping seniority update for %s job(s)",
            len(seniority_updates),
        )
        logger.info("-" * 60)
        logger.info(
            "Seniority Enrichment Summary: fetched=%s, upgraded=%s, failed=%s",
            stats["seniority_fetched"],
            stats["seniority_upgraded"],
            stats["seniority_failed"],
        )
        logger.info("=" * 60)
        return stats

    updated_rows = db.update_job_seniority_batch(seniority_updates)
    if updated_rows != len(seniority_updates):
        logger.warning(
            "Requested seniority updates for %s job(s) but only %s row(s) were affected",
            len(seniority_updates),
            updated_rows,
        )
    else:
        logger.info("Persisted seniority enrichment for %s job(s)", updated_rows)

    # Step 3 Summary
    logger.info("-" * 60)
    logger.info(
        "Seniority Enrichment Summary: fetched=%s, upgraded=%s, failed=%s",
        stats["seniority_fetched"],
        stats["seniority_upgraded"],
        stats["seniority_failed"],
    )
    logger.info("=" * 60)

    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("ENRICHMENT RUN COMPLETE - FINAL SUMMARY")
    logger.info("=" * 60)
    logger.info(
        "Skills:        jobs_fetched=%s, jobs_processed=%s, "
        "jobs_updated=%s, jobs_unchanged=%s",
        stats["skills_jobs_fetched"], stats["skills_jobs_processed"],
        stats["skills_jobs_updated"], stats["skills_jobs_unchanged"]
    )
    logger.info(
        "Companies:     companies_fetched=%s, companies_enriched=%s, "
        "companies_skipped=%s, companies_errors=%s",
        stats["companies_fetched"], stats["companies_enriched"],
        stats["companies_skipped"], stats["companies_errors"]
    )
    logger.info("Seniority:     jobs_fetched=%s, seniority_upgraded=%s, seniority_failed=%s",
                stats["seniority_fetched"], stats["seniority_upgraded"], stats["seniority_failed"])
    logger.info("=" * 60)
    logger.info("")

    return stats


def run_company_enrichment(
    *,
    db: EnricherDB,
    matcher: CompanyMatcher,
    limit: Optional[int] = None,
) -> dict[str, int]:
    """
    Execute the company enrichment workflow.

    First, ensures all unique companies from job_postings_stg have base records
    in companies_stg. Then, fetches companies from companies_stg that need
    Glassdoor enrichment, and calls Glassdoor API to enrich remaining companies.

    Args:
        db: Database access layer.
        matcher: Company matcher instance for fuzzy matching.
        limit: Optional maximum number of companies to process.

    Returns:
        Dictionary with counters: fetched, enriched, skipped, errors, base_records_created.
    """
    stats = {
        "fetched": 0,
        "enriched": 0,
        "skipped": 0,
        "errors": 0,
        "base_records_created": 0,
    }

    # Step 1: Ensure all unique companies from job_postings_stg have base records in companies_stg
    logger.info("Ensuring all unique companies have base records in staging.companies_stg")
    base_created = db.upsert_base_company_records()
    stats["base_records_created"] = base_created
    logger.info(
        "Created/updated %s base company records in staging.companies_stg", base_created
    )

    # Step 2: Fetch companies from companies_stg that need enrichment
    companies_to_enrich = db.fetch_companies_needing_enrichment(limit=limit)
    stats["fetched"] = len(companies_to_enrich)

    if not companies_to_enrich:
        logger.info("No companies found in staging.companies_stg needing enrichment")
        logger.info("-" * 60)
        logger.info(
            "Company Enrichment Summary: fetched=0, enriched=0, skipped=0, "
            "errors=0, base_records_created=%s",
            stats["base_records_created"],
        )
        logger.info("=" * 60)
        return stats

    logger.info(
        "Found %s companies in staging.companies_stg needing enrichment", stats["fetched"]
    )

    # Step 3: Process companies that need enrichment
    for company_data in companies_to_enrich:
        company_id = company_data["company_id"]
        company_name = company_data["name"]

        try:
            # Match company using fuzzy matching
            matched_company = matcher.match_company(company_name)

            if matched_company:
                # Upsert enriched data
                db.upsert_company_enrichment(company_id, matched_company)
                stats["enriched"] += 1
                logger.info(
                    "Enriched company: %s (ID: %s)", company_name, company_id
                )
            else:
                # Mark as attempted so we don't call Glassdoor again for this company
                db.mark_company_enrichment_skipped(company_id)
                stats["skipped"] += 1
                logger.info(
                    "No good Glassdoor match found for company: %s (ID: %s); marking as skipped",
                    company_name,
                    company_id,
                )

        except Exception as exc:
            # Per requirement 4c: log error and continue processing
            stats["errors"] += 1
            logger.error(
                "Error enriching company %s (ID: %s): %s",
                company_name,
                company_id,
                exc,
                exc_info=True,
            )

    # Step 2 Summary (called from run_company_enrichment)
    logger.info("-" * 60)
    logger.info(
        "Company Enrichment Summary: fetched=%s, enriched=%s, skipped=%s, "
        "errors=%s, base_records_created=%s",
        stats["fetched"],
        stats["enriched"],
        stats["skipped"],
        stats["errors"],
        stats["base_records_created"],
    )
    logger.info("=" * 60)

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

        # Initialize company enrichment if enabled
        matcher = None
        if args.enrich_companies:
            glassdoor_api_key = args.glassdoor_api_key or os.getenv("GLASSDOOR_API_KEY")
            if not glassdoor_api_key:
                logger.warning(
                    "Company enrichment enabled but GLASSDOOR_API_KEY not set; "
                    "skipping company enrichment"
                )
            else:
                try:
                    glassdoor_client = GlassdoorClient(api_key=glassdoor_api_key)
                    matcher = CompanyMatcher(glassdoor_client=glassdoor_client)
                    logger.info("Company enrichment enabled")
                except Exception as exc:
                    logger.error(
                        "Failed to initialize company enrichment: %s", exc, exc_info=True
                    )
                    logger.warning("Continuing without company enrichment")
                    matcher = None

        run_enricher(
            db=db,
            extractor=extractor,
            limit=args.limit,
            sources=args.source,
            include_existing=args.include_existing,
            dry_run=args.dry_run,
            enrich_companies=args.enrich_companies and matcher is not None,
            matcher=matcher,
        )

        # Detailed summary is already logged in run_enricher()
        logger.info("Enricher service completed successfully")
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

