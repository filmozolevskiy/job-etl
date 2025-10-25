"""
Database storage helper for saving job postings to PostgreSQL.

This module handles persistence of raw job postings to the raw.job_postings_raw table.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

from .base import JobPostingRaw

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class JobStorageError(Exception):
    """Custom exception for database storage errors."""

    pass


class JobStorage:
    """
    Handles storage of JobPostingRaw objects to PostgreSQL.

    Uses psycopg2 for direct database access and implements
    idempotent operations safe for re-running.

    Environment Variables Required:
        DATABASE_URL: PostgreSQL connection string
            Format: postgresql://user:password@host:port/database
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize the JobStorage helper.

        Args:
            database_url: PostgreSQL connection string (defaults to DATABASE_URL env var)

        Raises:
            ValueError: If DATABASE_URL is not set
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")

        if not self.database_url:
            raise ValueError(
                "DATABASE_URL must be set in environment or passed as parameter"
            )

        self.connection = None
        self.cursor = None

        logger.info(
            "JobStorage initialized",
            extra={
                "database": self._get_db_name_from_url(),
            },
        )

    def _get_db_name_from_url(self) -> str:
        """Extract database name from connection URL for logging."""
        try:
            # Format: postgresql://user:password@host:port/database
            return self.database_url.split("/")[-1].split("?")[0]
        except Exception:
            return "unknown"

    def connect(self) -> None:
        """
        Establish database connection.

        Raises:
            JobStorageError: If connection fails
        """
        try:
            self.connection = psycopg2.connect(self.database_url)
            self.cursor = self.connection.cursor()

            logger.info(
                "Database connection established",
                extra={"database": self._get_db_name_from_url()},
            )

        except psycopg2.Error as e:
            logger.error(
                "Failed to connect to database",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise JobStorageError(f"Database connection failed: {e}") from e

    def disconnect(self) -> None:
        """Close database connection and cursor."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

        logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry - establish connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.disconnect()
        return False

    def save_job(
        self,
        job: JobPostingRaw,
        collected_at: Optional[datetime] = None,
    ) -> str:
        """
        Save a single job posting to the database.

        Args:
            job: JobPostingRaw object to save
            collected_at: Timestamp when job was collected (defaults to now)

        Returns:
            UUID of the inserted row as string

        Raises:
            JobStorageError: If save operation fails
        """
        if not self.connection or not self.cursor:
            raise JobStorageError("Not connected to database. Call connect() first.")

        collected_at = collected_at or datetime.now(timezone.utc)

        try:
            # Insert job into raw.job_postings_raw
            insert_query = """
                INSERT INTO raw.job_postings_raw (source, payload, collected_at)
                VALUES (%s, %s, %s)
                RETURNING raw_id
            """

            # Use psycopg2.extras.Json for proper JSONB handling
            self.cursor.execute(
                insert_query,
                (
                    job.source,
                    Json(job.payload),
                    collected_at,
                ),
            )

            # Get the generated UUID
            raw_id = self.cursor.fetchone()[0]

            # Commit the transaction
            self.connection.commit()

            logger.info(
                "Job saved to database",
                extra={
                    "raw_id": str(raw_id),
                    "source": job.source,
                    "provider_job_id": job.provider_job_id,
                    "collected_at": collected_at.isoformat(),
                },
            )

            return str(raw_id)

        except psycopg2.Error as e:
            # Rollback on error
            if self.connection:
                self.connection.rollback()

            logger.error(
                "Failed to save job to database",
                extra={
                    "source": job.source,
                    "provider_job_id": job.provider_job_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise JobStorageError(f"Failed to save job: {e}") from e

    def save_jobs_batch(
        self,
        jobs: list[JobPostingRaw],
        collected_at: Optional[datetime] = None,
    ) -> list[str]:
        """
        Save multiple job postings in a single transaction.

        Args:
            jobs: List of JobPostingRaw objects to save
            collected_at: Timestamp when jobs were collected (defaults to now)

        Returns:
            List of UUIDs for the inserted rows

        Raises:
            JobStorageError: If batch save operation fails
        """
        if not self.connection or not self.cursor:
            raise JobStorageError("Not connected to database. Call connect() first.")

        if not jobs:
            logger.warning("save_jobs_batch called with empty list")
            return []

        collected_at = collected_at or datetime.now(timezone.utc)
        raw_ids = []

        try:
            # Insert each job and collect RETURNING values
            # Note: We use individual inserts instead of execute_batch to support RETURNING
            insert_query = """
                INSERT INTO raw.job_postings_raw (source, payload, collected_at)
                VALUES (%s, %s, %s)
                RETURNING raw_id
            """

            # Execute individual inserts within the same transaction
            for job in jobs:
                self.cursor.execute(
                    insert_query,
                    (job.source, Json(job.payload), collected_at),
                )
                raw_id = self.cursor.fetchone()[0]
                raw_ids.append(str(raw_id))

            # Commit the transaction
            self.connection.commit()

            logger.info(
                "Batch of jobs saved to database",
                extra={
                    "total_jobs": len(jobs),
                    "source": jobs[0].source if jobs else None,
                    "collected_at": collected_at.isoformat(),
                },
            )

            return raw_ids

        except psycopg2.Error as e:
            # Rollback on error
            if self.connection:
                self.connection.rollback()

            logger.error(
                "Failed to save batch of jobs to database",
                extra={
                    "total_jobs": len(jobs),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise JobStorageError(f"Failed to save batch: {e}") from e

    def get_job_count_by_source(self, source: Optional[str] = None) -> int:
        """
        Get count of jobs in the database, optionally filtered by source.

        Args:
            source: Filter by source name (optional)

        Returns:
            Count of jobs

        Raises:
            JobStorageError: If query fails
        """
        if not self.connection or not self.cursor:
            raise JobStorageError("Not connected to database. Call connect() first.")

        try:
            if source:
                query = "SELECT COUNT(*) FROM raw.job_postings_raw WHERE source = %s"
                self.cursor.execute(query, (source,))
            else:
                query = "SELECT COUNT(*) FROM raw.job_postings_raw"
                self.cursor.execute(query)

            count = self.cursor.fetchone()[0]

            logger.debug(
                "Retrieved job count",
                extra={
                    "source": source,
                    "count": count,
                },
            )

            return count

        except psycopg2.Error as e:
            logger.error(
                "Failed to get job count",
                extra={
                    "source": source,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise JobStorageError(f"Failed to get job count: {e}") from e

