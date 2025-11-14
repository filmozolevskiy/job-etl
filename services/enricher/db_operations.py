"""
Database operations for the enricher service.

Responsibilities:
    * Fetch normalized job postings that require enrichment
    * Update staging rows with enriched skills
    * Provide lightweight statistics useful for observability
"""
from __future__ import annotations

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

