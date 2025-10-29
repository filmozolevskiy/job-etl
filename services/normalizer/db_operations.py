"""
Database Operations for Normalizer Service

This module handles all database interactions for the normalizer:
- Reading raw job postings from raw.job_postings_raw
- Writing normalized data to staging.job_postings_stg with upsert logic
- Connection management and error handling

Key Features:
- Upsert logic: Insert new jobs, update last_seen_at for existing ones
- Batch processing: Process multiple jobs in one transaction
- Idempotent: Safe to run multiple times with same data
- Connection pooling: Efficient database resource usage
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator, Optional

import psycopg2
import psycopg2.extras
from psycopg2 import sql

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database operation fails."""
    pass


class NormalizerDB:
    """
    Database interface for the normalizer service.
    
    This class provides methods to:
    - Fetch unprocessed raw job postings
    - Insert/update normalized jobs in staging table
    - Track processing statistics
    
    Uses context managers for proper connection handling.
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
            raise DatabaseError(f"Failed to connect to database: {e}")
    
    def _test_connection(self) -> None:
        """Test database connection by executing a simple query."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
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
                extra={'error': str(e), 'error_type': type(e).__name__}
            )
            raise
        finally:
            if conn:
                conn.close()
    
    def fetch_raw_jobs(
        self,
        source: Optional[str] = None,
        limit: Optional[int] = None,
        min_collected_at: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Fetch raw job postings from raw.job_postings_raw table.
        
        Args:
            source: Filter by source name (e.g., 'jsearch'). If None, fetch all sources.
            limit: Maximum number of jobs to fetch. If None, fetch all.
            min_collected_at: Only fetch jobs collected after this timestamp (ISO format).
                            If None, fetch all jobs.
        
        Returns:
            List of dictionaries, each containing:
            - raw_id: UUID
            - source: str
            - payload: dict (parsed JSONB)
            - collected_at: datetime
        
        Raises:
            DatabaseError: If query fails
            
        Example:
            >>> db = NormalizerDB("postgresql://...")
            >>> jobs = db.fetch_raw_jobs(source='jsearch', limit=100)
            >>> len(jobs)
            100
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # Build query with optional filters
                    query = sql.SQL("""
                        SELECT 
                            raw_id,
                            source,
                            payload,
                            collected_at
                        FROM raw.job_postings_raw
                        WHERE 1=1
                        {source_filter}
                        {time_filter}
                        ORDER BY collected_at DESC
                        {limit_clause}
                    """).format(
                        source_filter=sql.SQL("AND source = %s") if source else sql.SQL(""),
                        time_filter=sql.SQL("AND collected_at >= %s") if min_collected_at else sql.SQL(""),
                        limit_clause=sql.SQL("LIMIT %s") if limit else sql.SQL("")
                    )
                    
                    # Build parameters list
                    params = []
                    if source:
                        params.append(source)
                    if min_collected_at:
                        params.append(min_collected_at)
                    if limit:
                        params.append(limit)
                    
                    cur.execute(query, params)
                    results = cur.fetchall()
                    
                    logger.info(
                        "Fetched raw job postings",
                        extra={
                            'count': len(results),
                            'source_filter': source,
                            'limit': limit,
                        }
                    )
                    
                    return [dict(row) for row in results]
                    
        except psycopg2.Error as e:
            logger.error(
                "Failed to fetch raw jobs",
                extra={'error': str(e), 'pgcode': e.pgcode}
            )
            raise DatabaseError(f"Failed to fetch raw jobs: {e}")
    
    def upsert_staging_job(self, job: dict[str, Any]) -> str:
        """
        Insert or update a normalized job in staging.job_postings_stg.
        
        Uses PostgreSQL's ON CONFLICT to implement upsert logic:
        - If hash_key already exists: Update last_seen_at and other fields
        - If new: Insert with first_seen_at and last_seen_at
        
        This ensures idempotency - running the same job multiple times is safe.
        
        Args:
            job: Normalized job dictionary containing all required fields
        
        Returns:
            The hash_key of the inserted/updated job
            
        Raises:
            DatabaseError: If insert/update fails
            
        Example:
            >>> normalized_job = {
            ...     'hash_key': 'a1b2c3d4...',
            ...     'job_title': 'Data Engineer',
            ...     'company': 'Acme Corp',
            ...     # ... other fields
            ... }
            >>> hash_key = db.upsert_staging_job(normalized_job)
            >>> print(hash_key)
            'a1b2c3d4...'
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Insert or update query with ON CONFLICT
                    # This is the key to idempotency!
                    query = """
                        INSERT INTO staging.job_postings_stg (
                            hash_key,
                            provider_job_id,
                            job_link,
                            job_title,
                            company,
                            company_size,
                            location,
                            remote_type,
                            contract_type,
                            salary_min,
                            salary_max,
                            salary_currency,
                            description,
                            skills_raw,
                            posted_at,
                            apply_url,
                            source,
                            first_seen_at,
                            last_seen_at
                        ) VALUES (
                            %(hash_key)s,
                            %(provider_job_id)s,
                            %(job_link)s,
                            %(job_title)s,
                            %(company)s,
                            %(company_size)s,
                            %(location)s,
                            %(remote_type)s,
                            %(contract_type)s,
                            %(salary_min)s,
                            %(salary_max)s,
                            %(salary_currency)s,
                            %(description)s,
                            %(skills_raw)s,
                            %(posted_at)s,
                            %(apply_url)s,
                            %(source)s,
                            NOW(),
                            NOW()
                        )
                        ON CONFLICT (hash_key)
                        DO UPDATE SET
                            last_seen_at = NOW(),
                            -- Update fields if newer data is available
                            provider_job_id = COALESCE(EXCLUDED.provider_job_id, staging.job_postings_stg.provider_job_id),
                            job_link = COALESCE(EXCLUDED.job_link, staging.job_postings_stg.job_link),
                            job_title = EXCLUDED.job_title,
                            company = EXCLUDED.company,
                            company_size = COALESCE(EXCLUDED.company_size, staging.job_postings_stg.company_size),
                            location = EXCLUDED.location,
                            remote_type = COALESCE(EXCLUDED.remote_type, staging.job_postings_stg.remote_type),
                            contract_type = COALESCE(EXCLUDED.contract_type, staging.job_postings_stg.contract_type),
                            salary_min = COALESCE(EXCLUDED.salary_min, staging.job_postings_stg.salary_min),
                            salary_max = COALESCE(EXCLUDED.salary_max, staging.job_postings_stg.salary_max),
                            salary_currency = COALESCE(EXCLUDED.salary_currency, staging.job_postings_stg.salary_currency),
                            description = COALESCE(EXCLUDED.description, staging.job_postings_stg.description),
                            skills_raw = COALESCE(EXCLUDED.skills_raw, staging.job_postings_stg.skills_raw),
                            posted_at = COALESCE(EXCLUDED.posted_at, staging.job_postings_stg.posted_at),
                            apply_url = COALESCE(EXCLUDED.apply_url, staging.job_postings_stg.apply_url),
                            source = EXCLUDED.source
                        RETURNING hash_key
                    """
                    
                    cur.execute(query, job)
                    result = cur.fetchone()
                    hash_key = result[0] if result else job['hash_key']
                    
                    logger.debug(
                        "Upserted job to staging",
                        extra={
                            'hash_key': hash_key,
                            'company': job.get('company'),
                            'job_title': job.get('job_title'),
                        }
                    )
                    
                    return hash_key
                    
        except psycopg2.IntegrityError as e:
            logger.error(
                "Data integrity error during upsert",
                extra={
                    'error': str(e),
                    'pgcode': e.pgcode,
                    'hash_key': job.get('hash_key'),
                }
            )
            raise DatabaseError(f"Data integrity error: {e}")
        except psycopg2.Error as e:
            logger.error(
                "Failed to upsert staging job",
                extra={
                    'error': str(e),
                    'pgcode': e.pgcode,
                    'hash_key': job.get('hash_key'),
                }
            )
            raise DatabaseError(f"Failed to upsert job: {e}")
    
    def upsert_staging_jobs_batch(self, jobs: list[dict[str, Any]]) -> int:
        """
        Insert or update multiple normalized jobs in a single transaction.
        
        This is more efficient than calling upsert_staging_job() multiple times
        because it uses a single database transaction.
        
        Args:
            jobs: List of normalized job dictionaries
        
        Returns:
            Number of jobs successfully upserted
            
        Raises:
            DatabaseError: If batch upsert fails
            
        Example:
            >>> jobs = [normalized_job1, normalized_job2, ...]
            >>> count = db.upsert_staging_jobs_batch(jobs)
            >>> print(f"Upserted {count} jobs")
        """
        if not jobs:
            logger.warning("No jobs to upsert")
            return 0
        
        success_count = 0
        failed_count = 0
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for job in jobs:
                        try:
                            # Use the same upsert query as single insert
                            # Could be optimized further with execute_batch, but this is clearer
                            query = """
                                INSERT INTO staging.job_postings_stg (
                                    hash_key, provider_job_id, job_link, job_title, company,
                                    company_size, location, remote_type, contract_type,
                                    salary_min, salary_max, salary_currency, description,
                                    skills_raw, posted_at, apply_url, source,
                                    first_seen_at, last_seen_at
                                ) VALUES (
                                    %(hash_key)s, %(provider_job_id)s, %(job_link)s, %(job_title)s,
                                    %(company)s, %(company_size)s, %(location)s, %(remote_type)s,
                                    %(contract_type)s, %(salary_min)s, %(salary_max)s,
                                    %(salary_currency)s, %(description)s, %(skills_raw)s,
                                    %(posted_at)s, %(apply_url)s, %(source)s, NOW(), NOW()
                                )
                                ON CONFLICT (hash_key)
                                DO UPDATE SET
                                    last_seen_at = NOW(),
                                    provider_job_id = COALESCE(EXCLUDED.provider_job_id, staging.job_postings_stg.provider_job_id),
                                    job_link = COALESCE(EXCLUDED.job_link, staging.job_postings_stg.job_link),
                                    job_title = EXCLUDED.job_title,
                                    company = EXCLUDED.company,
                                    company_size = COALESCE(EXCLUDED.company_size, staging.job_postings_stg.company_size),
                                    location = EXCLUDED.location,
                                    remote_type = COALESCE(EXCLUDED.remote_type, staging.job_postings_stg.remote_type),
                                    contract_type = COALESCE(EXCLUDED.contract_type, staging.job_postings_stg.contract_type),
                                    salary_min = COALESCE(EXCLUDED.salary_min, staging.job_postings_stg.salary_min),
                                    salary_max = COALESCE(EXCLUDED.salary_max, staging.job_postings_stg.salary_max),
                                    salary_currency = COALESCE(EXCLUDED.salary_currency, staging.job_postings_stg.salary_currency),
                                    description = COALESCE(EXCLUDED.description, staging.job_postings_stg.description),
                                    skills_raw = COALESCE(EXCLUDED.skills_raw, staging.job_postings_stg.skills_raw),
                                    posted_at = COALESCE(EXCLUDED.posted_at, staging.job_postings_stg.posted_at),
                                    apply_url = COALESCE(EXCLUDED.apply_url, staging.job_postings_stg.apply_url),
                                    source = EXCLUDED.source
                            """
                            
                            cur.execute(query, job)
                            success_count += 1
                            
                        except psycopg2.Error as e:
                            failed_count += 1
                            logger.warning(
                                "Failed to upsert individual job in batch",
                                extra={
                                    'error': str(e),
                                    'hash_key': job.get('hash_key'),
                                    'company': job.get('company'),
                                }
                            )
                            # Continue processing other jobs
                    
                    logger.info(
                        "Batch upsert completed",
                        extra={
                            'total': len(jobs),
                            'success': success_count,
                            'failed': failed_count,
                        }
                    )
                    
                    return success_count
                    
        except psycopg2.Error as e:
            logger.error(
                "Batch upsert transaction failed",
                extra={'error': str(e), 'pgcode': e.pgcode}
            )
            raise DatabaseError(f"Batch upsert failed: {e}")
    
    def get_staging_stats(self) -> dict[str, Any]:
        """
        Get statistics about staging table contents.
        
        Useful for monitoring and reporting.
        
        Returns:
            Dictionary with statistics:
            - total_jobs: Total number of unique jobs
            - jobs_by_source: Count per source
            - latest_update: Most recent last_seen_at timestamp
            
        Example:
            >>> stats = db.get_staging_stats()
            >>> print(f"Total jobs: {stats['total_jobs']}")
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_jobs,
                            COUNT(DISTINCT source) as source_count,
                            MAX(last_seen_at) as latest_update,
                            MIN(first_seen_at) as earliest_job
                        FROM staging.job_postings_stg
                    """)
                    overall = dict(cur.fetchone())
                    
                    cur.execute("""
                        SELECT 
                            source,
                            COUNT(*) as job_count
                        FROM staging.job_postings_stg
                        GROUP BY source
                        ORDER BY job_count DESC
                    """)
                    by_source = [dict(row) for row in cur.fetchall()]
                    
                    return {
                        'total_jobs': overall['total_jobs'],
                        'source_count': overall['source_count'],
                        'latest_update': overall['latest_update'],
                        'earliest_job': overall['earliest_job'],
                        'jobs_by_source': by_source,
                    }
                    
        except psycopg2.Error as e:
            logger.error(
                "Failed to get staging stats",
                extra={'error': str(e)}
            )
            raise DatabaseError(f"Failed to get stats: {e}")

