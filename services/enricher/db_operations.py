"""
Database operations for the enricher service.

Responsibilities:
    * Fetch normalized job postings that require enrichment
    * Update staging rows with enriched skills
    * Provide lightweight statistics useful for observability
"""
from __future__ import annotations

import json
import logging
from collections.abc import Generator, Iterable, Sequence
from contextlib import contextmanager
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from psycopg2 import sql

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database interaction fails."""


class EnricherDB:
    """
    Thin wrapper around psycopg2 for the enricher service.

    The normalizer populates ``staging.job_postings_stg`` with raw data.  The
    enricher reads those rows (typically filtering to records with missing
    skills) and writes updates back to the same table so downstream dbt models
    can consume the enriched attributes.
    """

    def __init__(self, connection_string: str):
        """
        Initialise database connection details.

        Args:
            connection_string: PostgreSQL connection URL.
        """
        self.connection_string = connection_string
        try:
            self._test_connection()
        except Exception as exc:  # pragma: no cover - sanity check
            raise DatabaseError(f"Failed to connect to database: {exc}") from exc

    def _test_connection(self) -> None:
        with self._get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")

    @contextmanager
    def _get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            yield conn
            conn.commit()
        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error(
                "Database operation failed; rolled back transaction",
                extra={"error": str(exc), "error_type": type(exc).__name__},
            )
            raise DatabaseError(str(exc)) from exc
        finally:
            if conn:
                conn.close()

    def fetch_jobs_for_skills(
        self,
        *,
        sources: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        only_missing: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Retrieve job postings that require skill extraction.

        Args:
            sources: Optional list of provider sources to filter by.
            limit: Maximum number of rows to fetch.
            only_missing: When True, restrict to rows without skills.

        Returns:
            List of dict rows containing ``hash_key``, ``description``,
            ``skills_raw``, and metadata helpful for logging.
        """
        conditions = [sql.SQL("description IS NOT NULL")]
        params: list[Any] = []

        if only_missing:
            conditions.append(
                sql.SQL("(skills_raw IS NULL OR array_length(skills_raw, 1) = 0)")
            )

        if sources:
            conditions.append(sql.SQL("source = ANY(%s)"))
            params.append(sources)

        where_clause = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)

        query_parts = [
            sql.SQL(
                """
                SELECT
                    hash_key,
                    job_title,
                    company,
                    source,
                    description,
                    skills_raw
                FROM staging.job_postings_stg
                """
            ),
            where_clause,
            sql.SQL(" ORDER BY last_seen_at DESC"),
        ]

        if limit:
            query_parts.append(sql.SQL(" LIMIT %s"))
            params.append(limit)

        query = sql.SQL("").join(query_parts)

        try:
            with self._get_connection() as conn, conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except psycopg2.Error as exc:
            raise DatabaseError(f"Failed to fetch jobs for enrichment: {exc}") from exc

    def update_job_skills_batch(
        self, updates: Iterable[tuple[str, Sequence[str]]]
    ) -> int:
        """
        Persist enriched skills for multiple jobs in a single transaction.

        Note: This method unconditionally overwrites ``skills_raw`` with the
        extracted skills. If a provider previously supplied skills in this field,
        they will be replaced by the enricher's extraction results. This is intentional:
        the enricher extracts skills from the full job description, which is typically
        more comprehensive than provider-supplied skill lists.

        Args:
            updates: Iterable of ``(hash_key, skills)`` tuples. Empty skill lists
                are converted to NULL in the database.

        Returns:
            Number of rows updated.
        """
        updates = list(updates)
        if not updates:
            return 0

        query = """
            UPDATE staging.job_postings_stg
            SET skills_raw = %s
            WHERE hash_key = %s
        """

        params = [(skills or None, hash_key) for hash_key, skills in updates]

        try:
            with self._get_connection() as conn, conn.cursor() as cursor:
                cursor.executemany(query, params)
                return cursor.rowcount
        except psycopg2.Error as exc:
            raise DatabaseError(f"Failed to update enriched skills: {exc}") from exc

    def upsert_base_company_records(self) -> int:
        """
        Create base company records in companies_stg from job_postings_stg.

        This ensures all unique companies from job_postings_stg have base records
        in companies_stg before enrichment. This is idempotent - existing records
        are not overwritten.

        Returns:
            Number of base company records created (0 if all already exist).
        """
        query = """
            INSERT INTO staging.companies_stg (company_id, name, company_size, source_first_seen, created_at)
            SELECT DISTINCT ON (company_id)
                MD5(LOWER(REGEXP_REPLACE(TRIM(COALESCE(company, 'unknown')), '\\s+', ' ', 'g'))) AS company_id,
                COALESCE(company, 'unknown') AS name,
                company_size,
                source AS source_first_seen,
                first_seen_at AS created_at
            FROM staging.job_postings_stg
            WHERE company IS NOT NULL
            ORDER BY company_id, first_seen_at ASC
            ON CONFLICT (company_id) DO NOTHING
        """
        try:
            with self._get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query)
                return cursor.rowcount
        except psycopg2.Error as exc:
            raise DatabaseError(f"Failed to upsert base company records: {exc}") from exc

    def fetch_companies_needing_enrichment(
        self, limit: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Fetch companies from companies_stg that need Glassdoor enrichment.

        Returns companies where enriched_at IS NULL, meaning they have base records
        but haven't been enriched with Glassdoor API data yet.

        Args:
            limit: Optional maximum number of companies to fetch.

        Returns:
            List of dicts with keys: "company_id" (str), "name" (str), "company_size" (str)
        """
        query = """
            SELECT company_id, name, company_size
            FROM staging.companies_stg
            WHERE enriched_at IS NULL
            ORDER BY created_at ASC
        """
        params: list[Any] = []
        if limit:
            query += " LIMIT %s"
            params.append(limit)

        try:
            with self._get_connection() as conn, conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except psycopg2.Error as exc:
            raise DatabaseError(
                f"Failed to fetch companies needing enrichment: {exc}"
            ) from exc

    def upsert_company_enrichment(
        self, company_id: str, glassdoor_data: dict[str, Any]
    ) -> int:
        """
        Upsert company enrichment data into staging.companies_stg.

        Maps Glassdoor API response fields to table columns and handles JSONB fields.

        Args:
            company_id: Our MD5 hash company_id (primary key)
            glassdoor_data: Company data dict from Glassdoor API

        Returns:
            Number of rows affected (should be 1 on success).
        """

        # Map API response fields to database columns
        # Handle JSONB fields by converting lists to JSON strings
        competitors_json = None
        if glassdoor_data.get("competitors"):
            competitors_json = json.dumps(glassdoor_data["competitors"])

        office_locations_json = None
        if glassdoor_data.get("office_locations"):
            office_locations_json = json.dumps(glassdoor_data["office_locations"])

        awards_json = None
        if glassdoor_data.get("best_places_to_work_awards"):
            awards_json = json.dumps(glassdoor_data["best_places_to_work_awards"])

        query = """
            INSERT INTO staging.companies_stg (
                company_id,
                glassdoor_company_id,
                name,
                company_link,
                rating,
                review_count,
                salary_count,
                job_count,
                headquarters_location,
                logo,
                company_size,
                company_size_category,
                company_description,
                industry,
                website,
                company_type,
                revenue,
                business_outlook_rating,
                career_opportunities_rating,
                ceo,
                ceo_rating,
                compensation_and_benefits_rating,
                culture_and_values_rating,
                diversity_and_inclusion_rating,
                recommend_to_friend_rating,
                senior_management_rating,
                work_life_balance_rating,
                stock,
                year_founded,
                reviews_link,
                jobs_link,
                faq_link,
                competitors,
                office_locations,
                best_places_to_work_awards,
                enriched_at,
                created_at,
                updated_at
            ) VALUES (
                %(company_id)s,
                %(glassdoor_company_id)s,
                %(name)s,
                %(company_link)s,
                %(rating)s,
                %(review_count)s,
                %(salary_count)s,
                %(job_count)s,
                %(headquarters_location)s,
                %(logo)s,
                %(company_size)s,
                %(company_size_category)s,
                %(company_description)s,
                %(industry)s,
                %(website)s,
                %(company_type)s,
                %(revenue)s,
                %(business_outlook_rating)s,
                %(career_opportunities_rating)s,
                %(ceo)s,
                %(ceo_rating)s,
                %(compensation_and_benefits_rating)s,
                %(culture_and_values_rating)s,
                %(diversity_and_inclusion_rating)s,
                %(recommend_to_friend_rating)s,
                %(senior_management_rating)s,
                %(work_life_balance_rating)s,
                %(stock)s,
                %(year_founded)s,
                %(reviews_link)s,
                %(jobs_link)s,
                %(faq_link)s,
                %(competitors)s::jsonb,
                %(office_locations)s::jsonb,
                %(best_places_to_work_awards)s::jsonb,
                NOW(),
                COALESCE((SELECT created_at FROM staging.companies_stg WHERE company_id = %(company_id)s), NOW()),
                NOW()
            )
            ON CONFLICT (company_id)
            DO UPDATE SET
                glassdoor_company_id = EXCLUDED.glassdoor_company_id,
                name = EXCLUDED.name,
                company_link = EXCLUDED.company_link,
                rating = EXCLUDED.rating,
                review_count = EXCLUDED.review_count,
                salary_count = EXCLUDED.salary_count,
                job_count = EXCLUDED.job_count,
                headquarters_location = EXCLUDED.headquarters_location,
                logo = EXCLUDED.logo,
                company_size = EXCLUDED.company_size,
                company_size_category = EXCLUDED.company_size_category,
                company_description = EXCLUDED.company_description,
                industry = EXCLUDED.industry,
                website = EXCLUDED.website,
                company_type = EXCLUDED.company_type,
                revenue = EXCLUDED.revenue,
                business_outlook_rating = EXCLUDED.business_outlook_rating,
                career_opportunities_rating = EXCLUDED.career_opportunities_rating,
                ceo = EXCLUDED.ceo,
                ceo_rating = EXCLUDED.ceo_rating,
                compensation_and_benefits_rating = EXCLUDED.compensation_and_benefits_rating,
                culture_and_values_rating = EXCLUDED.culture_and_values_rating,
                diversity_and_inclusion_rating = EXCLUDED.diversity_and_inclusion_rating,
                recommend_to_friend_rating = EXCLUDED.recommend_to_friend_rating,
                senior_management_rating = EXCLUDED.senior_management_rating,
                work_life_balance_rating = EXCLUDED.work_life_balance_rating,
                stock = EXCLUDED.stock,
                year_founded = EXCLUDED.year_founded,
                reviews_link = EXCLUDED.reviews_link,
                jobs_link = EXCLUDED.jobs_link,
                faq_link = EXCLUDED.faq_link,
                competitors = EXCLUDED.competitors,
                office_locations = EXCLUDED.office_locations,
                best_places_to_work_awards = EXCLUDED.best_places_to_work_awards,
                enriched_at = NOW(),
                updated_at = NOW()
            RETURNING company_id
        """

        params = {
            "company_id": company_id,
            "glassdoor_company_id": glassdoor_data.get("company_id"),
            "name": glassdoor_data.get("name"),
            "company_link": glassdoor_data.get("company_link"),
            "rating": glassdoor_data.get("rating"),
            "review_count": glassdoor_data.get("review_count"),
            "salary_count": glassdoor_data.get("salary_count"),
            "job_count": glassdoor_data.get("job_count"),
            "headquarters_location": glassdoor_data.get("headquarters_location"),
            "logo": glassdoor_data.get("logo"),
            "company_size": glassdoor_data.get("company_size"),
            "company_size_category": glassdoor_data.get("company_size_category"),
            "company_description": glassdoor_data.get("company_description"),
            "industry": glassdoor_data.get("industry"),
            "website": glassdoor_data.get("website"),
            "company_type": glassdoor_data.get("company_type"),
            "revenue": glassdoor_data.get("revenue"),
            "business_outlook_rating": glassdoor_data.get("business_outlook_rating"),
            "career_opportunities_rating": glassdoor_data.get(
                "career_opportunities_rating"
            ),
            "ceo": glassdoor_data.get("ceo"),
            "ceo_rating": glassdoor_data.get("ceo_rating"),
            "compensation_and_benefits_rating": glassdoor_data.get(
                "compensation_and_benefits_rating"
            ),
            "culture_and_values_rating": glassdoor_data.get("culture_and_values_rating"),
            "diversity_and_inclusion_rating": glassdoor_data.get(
                "diversity_and_inclusion_rating"
            ),
            "recommend_to_friend_rating": glassdoor_data.get(
                "recommend_to_friend_rating"
            ),
            "senior_management_rating": glassdoor_data.get("senior_management_rating"),
            "work_life_balance_rating": glassdoor_data.get("work_life_balance_rating"),
            "stock": glassdoor_data.get("stock"),
            "year_founded": glassdoor_data.get("year_founded"),
            "reviews_link": glassdoor_data.get("reviews_link"),
            "jobs_link": glassdoor_data.get("jobs_link"),
            "faq_link": glassdoor_data.get("faq_link"),
            "competitors": competitors_json,
            "office_locations": office_locations_json,
            "best_places_to_work_awards": awards_json,
        }

        try:
            with self._get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                return 1 if result else 0
        except psycopg2.Error as exc:
            raise DatabaseError(
                f"Failed to upsert company enrichment: {exc}"
            ) from exc

