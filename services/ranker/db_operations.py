"""
Database Operations for Ranker Service

This module handles all database interactions for the ranker:
- Reading unranked jobs from marts.fact_jobs
- Updating jobs with rank_score and rank_explain
- Connection management and error handling
"""

import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from psycopg2 import sql

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database operation fails."""

    pass


class RankerDB:
    """
    Database interface for the ranker service.

    This class provides methods to:
    - Fetch unranked jobs from marts.fact_jobs
    - Update jobs with rank scores and explanations
    - Track processing statistics
    """

    def __init__(self, connection_string: str):
        """
        Initialize database connection.

        Args:
            connection_string: PostgreSQL connection URL
                             Format: postgresql://user:pass@host:port/dbname

        Raises:
            DatabaseError: If connection fails
        """
        self.connection_string = connection_string
        self._conn: Optional[psycopg2.extensions.connection] = None

        # Validate connection
        try:
            self._test_connection()
            logger.info("Database connection validated successfully")
        except Exception as e:
            raise DatabaseError(f"Failed to connect to database: {e}") from e

    def _test_connection(self) -> None:
        """Test database connection by executing a simple query."""
        with self._get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")

    @contextmanager
    def _get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """
        Context manager for database connections.

        Ensures connections are properly closed and transactions are committed/rolled back.

        Yields:
            Database connection
        """
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(
                "Database operation failed, rolled back transaction",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise
        finally:
            if conn:
                conn.close()

    def fetch_unranked_jobs(
        self,
        limit: Optional[int] = None,
        where_rank_score_is_null: bool = True,
        min_ingested_at: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch unranked jobs from marts.fact_jobs.

        Args:
            limit: Maximum number of jobs to fetch. If None, fetch all.
            where_rank_score_is_null: If True, only fetch jobs with NULL rank_score.
            min_ingested_at: Only fetch jobs ingested on/after this timestamp (ISO format).
                           If None, fetch all jobs (subject to other filters).

        Returns:
            List of dictionaries containing job data

        Raises:
            DatabaseError: If query fails

        Example:
            >>> db = RankerDB("postgresql://...")
            >>> jobs = db.fetch_unranked_jobs(limit=100)
            >>> len(jobs)
            100
        """
        try:
            with (
                self._get_connection() as conn,
                conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur,
            ):
                # Build query with LEFT JOIN to dim_companies for company_size
                query_conditions = [sql.SQL("WHERE 1=1")]
                params = []
                if where_rank_score_is_null:
                    query_conditions.append(sql.SQL("AND rank_score IS NULL"))
                if min_ingested_at:
                    query_conditions.append(sql.SQL("AND f.ingested_at >= %s"))
                    params.append(min_ingested_at)

                query_parts = (
                    [
                        sql.SQL("SELECT"),
                        sql.SQL(
                            "f.hash_key, f.job_title_std, f.company_id, "
                            "f.location_std, f.remote_type,"
                        ),
                        sql.SQL(
                            "f.contract_type, f.salary_min_norm, f.salary_max_norm, "
                            "f.salary_currency_norm,"
                        ),
                        sql.SQL("f.skills, f.posted_at, f.source, f.apply_url, d.company_size"),
                        sql.SQL("FROM marts.fact_jobs f"),
                        sql.SQL("LEFT JOIN marts.dim_companies d ON f.company_id = d.company_id"),
                    ]
                    + query_conditions
                    + [
                        sql.SQL("ORDER BY f.ingested_at DESC"),
                    ]
                )

                if limit:
                    query_parts.append(sql.SQL("LIMIT %s"))
                    params.append(limit)

                query = sql.SQL(" ").join(query_parts)

                # Execute with parameters
                cur.execute(query, params)
                results = cur.fetchall()

                logger.info(
                    "Fetched unranked jobs",
                    extra={
                        "count": len(results),
                        "limit": limit,
                        "min_ingested_at": min_ingested_at,
                    },
                )

                # Convert to list of dicts
                jobs = [dict(row) for row in results]
                return jobs

        except psycopg2.Error as e:
            logger.error(
                "Failed to fetch unranked jobs", extra={"error": str(e), "pgcode": e.pgcode}
            )
            raise DatabaseError(f"Failed to fetch unranked jobs: {e}") from e

    def update_job_ranking(
        self, hash_key: str, rank_score: float, rank_explain: dict[str, float]
    ) -> None:
        """
        Update a job's rank_score and rank_explain.

        Args:
            hash_key: Unique identifier for the job
            rank_score: Overall ranking score (0-100)
            rank_explain: Dictionary of per-feature subscores

        Raises:
            DatabaseError: If update fails

        Example:
            >>> db.update_job_ranking('abc123', 85.5, {'title_keywords': 0.9, ...})
        """
        try:
            with self._get_connection() as conn, conn.cursor() as cur:
                # Convert rank_explain to JSONB
                rank_explain_json = json.dumps(rank_explain)

                query = """
                    UPDATE marts.fact_jobs
                    SET rank_score = %s, rank_explain = %s
                    WHERE hash_key = %s
                """

                cur.execute(query, (rank_score, rank_explain_json, hash_key))

                if cur.rowcount == 0:
                    logger.warning(
                        "No rows updated - hash_key not found", extra={"hash_key": hash_key}
                    )
                else:
                    logger.debug(
                        "Updated job ranking",
                        extra={
                            "hash_key": hash_key,
                            "rank_score": rank_score,
                        },
                    )

        except psycopg2.Error as e:
            logger.error(
                "Failed to update job ranking",
                extra={
                    "error": str(e),
                    "pgcode": e.pgcode,
                    "hash_key": hash_key,
                },
            )
            raise DatabaseError(f"Failed to update job ranking: {e}") from e

    def update_jobs_ranking_batch(self, rankings: list[dict[str, Any]]) -> int:
        """
        Update multiple jobs' rankings in a single transaction.

        Args:
            rankings: List of dicts with keys: hash_key, rank_score, rank_explain

        Returns:
            Number of jobs successfully updated

        Raises:
            DatabaseError: If batch update fails

        Example:
            >>> rankings = [
            ...     {'hash_key': 'abc', 'rank_score': 85.5, 'rank_explain': {...}},
            ...     {'hash_key': 'def', 'rank_score': 92.0, 'rank_explain': {...}},
            ... ]
            >>> count = db.update_jobs_ranking_batch(rankings)
        """
        if not rankings:
            logger.warning("No rankings to update")
            return 0

        success_count = 0
        failed_count = 0

        try:
            with self._get_connection() as conn, conn.cursor() as cur:
                for ranking in rankings:
                    try:
                        hash_key = ranking["hash_key"]
                        rank_score = ranking["rank_score"]
                        rank_explain = ranking["rank_explain"]

                        # Convert rank_explain to JSONB
                        rank_explain_json = json.dumps(rank_explain)

                        query = """
                            UPDATE marts.fact_jobs
                            SET rank_score = %s, rank_explain = %s
                            WHERE hash_key = %s
                        """

                        cur.execute(query, (rank_score, rank_explain_json, hash_key))
                        if cur.rowcount > 0:
                            success_count += 1
                        else:
                            failed_count += 1
                            logger.warning(
                                "No rows updated for hash_key", extra={"hash_key": hash_key}
                            )

                    except Exception as e:
                        failed_count += 1
                        logger.warning(
                            "Failed to update individual job in batch",
                            extra={
                                "error": str(e),
                                "hash_key": ranking.get("hash_key"),
                            },
                        )
                        # Continue processing other jobs

                logger.info(
                    "Batch update completed",
                    extra={
                        "total": len(rankings),
                        "success": success_count,
                        "failed": failed_count,
                    },
                )

                return success_count

        except psycopg2.Error as e:
            logger.error(
                "Batch update transaction failed", extra={"error": str(e), "pgcode": e.pgcode}
            )
            raise DatabaseError(f"Batch update failed: {e}") from e

    def get_ranking_stats(self) -> dict[str, Any]:
        """
        Get statistics about ranking status.

        Useful for monitoring and reporting.

        Returns:
            Dictionary with statistics:
            - total_jobs: Total number of jobs
            - ranked_jobs: Number of jobs with rank_score
            - unranked_jobs: Number of jobs without rank_score
            - average_score: Average rank_score
            - top_score: Highest rank_score
            - bottom_score: Lowest rank_score

        Example:
            >>> stats = db.get_ranking_stats()
            >>> print(f"Ranked: {stats['ranked_jobs']}/{stats['total_jobs']}")
        """
        try:
            with (
                self._get_connection() as conn,
                conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur,
            ):
                cur.execute("""
                    SELECT
                        COUNT(*) as total_jobs,
                        COUNT(rank_score) as ranked_jobs,
                        COUNT(*) - COUNT(rank_score) as unranked_jobs,
                        AVG(rank_score) as average_score,
                        MAX(rank_score) as top_score,
                        MIN(rank_score) as bottom_score
                    FROM marts.fact_jobs
                """)
                results = dict(cur.fetchone())

                return {
                    "total_jobs": results["total_jobs"],
                    "ranked_jobs": results["ranked_jobs"],
                    "unranked_jobs": results["unranked_jobs"],
                    "average_score": float(results["average_score"])
                    if results["average_score"]
                    else None,
                    "top_score": float(results["top_score"]) if results["top_score"] else None,
                    "bottom_score": float(results["bottom_score"])
                    if results["bottom_score"]
                    else None,
                }

        except psycopg2.Error as e:
            logger.error("Failed to get ranking stats", extra={"error": str(e)})
            raise DatabaseError(f"Failed to get stats: {e}") from e
