"""
Backfill script to update seniority_level for existing job postings.

This script:
1. Reads all job postings from staging.job_postings_stg where seniority_level = 'unknown'
2. Re-extracts seniority level using the improved extraction logic
3. Updates the database with the new seniority levels

Usage:
    python scripts/backfill_seniority_levels.py
"""

import os
import sys
from pathlib import Path

# Add services to path so we can import the extraction function
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "services" / "normalizer"))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
from seniority_extractor import extract_seniority_level  # noqa: E402

# Database connection parameters
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "job_etl")
DB_USER = os.getenv("POSTGRES_USER", "job_etl_user")

# Read password from secrets file
PASSWORD_FILE = project_root / "secrets" / "database" / "postgres_password.txt"


def get_db_connection():
    """Create and return a database connection."""
    if not PASSWORD_FILE.exists():
        raise FileNotFoundError(f"Password file not found: {PASSWORD_FILE}")

    with open(PASSWORD_FILE) as f:
        password = f.read().strip()

    conn_string = (
        f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={password}"
    )
    return psycopg2.connect(conn_string)


def backfill_seniority_levels(dry_run: bool = False):
    """
    Backfill seniority levels for records with 'unknown' seniority.

    Args:
        dry_run: If True, only show what would be updated without making changes
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch all records with unknown seniority
        cur.execute("""
            SELECT hash_key, job_title, seniority_level
            FROM staging.job_postings_stg
            WHERE seniority_level = 'unknown'
            ORDER BY last_seen_at DESC
        """)

        records = cur.fetchall()
        print(f"Found {len(records)} records with seniority_level = 'unknown'")

        if not records:
            print("No records to update.")
            return

        # Process each record
        updates = []
        stats = {"junior": 0, "intermediate": 0, "senior": 0, "unknown": 0}

        for record in records:
            job_title = record["job_title"]
            new_seniority = extract_seniority_level(job_title)

            if new_seniority != "unknown":
                updates.append((record["hash_key"], new_seniority, job_title))
                stats[new_seniority] += 1
            else:
                stats["unknown"] += 1

        print("\nExtraction results:")
        print(f"  - Will be updated: {len(updates)}")
        print(f"    * Junior: {stats['junior']}")
        print(f"    * Intermediate: {stats['intermediate']}")
        print(f"    * Senior: {stats['senior']}")
        print(f"  - Remaining unknown: {stats['unknown']}")

        if dry_run:
            print("\n[DRY RUN] Would update the following records:")
            for _hash_key, new_level, title in updates[:10]:  # Show first 10
                print(f"  {title[:60]:<60} -> {new_level}")
            if len(updates) > 10:
                print(f"  ... and {len(updates) - 10} more")
            return

        # Perform updates
        if updates:
            print(f"\nUpdating {len(updates)} records...")
            cur.execute("BEGIN")

            update_count = 0
            for hash_key, new_level, _title in updates:
                cur.execute(
                    """
                    UPDATE staging.job_postings_stg
                    SET seniority_level = %s
                    WHERE hash_key = %s
                """,
                    (new_level, hash_key),
                )
                update_count += 1

            conn.commit()
            print(f"✓ Successfully updated {update_count} records")
        else:
            print("\nNo records to update.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error: {e}", file=sys.stderr)
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill seniority levels for job postings with 'unknown' seniority"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be updated without making changes"
    )
    args = parser.parse_args()

    backfill_seniority_levels(dry_run=args.dry_run)
