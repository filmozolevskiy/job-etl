"""
Job-ETL Daily DAG

This DAG orchestrates the daily ETL pipeline for job postings:
1. Extracts job data from configured sources (JSearch API)
2. Normalizes data to canonical format (Python normalizer service)
3. Enriches with skills, standardized titles, locations, salary
4. Runs core dbt models (dimensions and facts)
5. Deduplicates based on hash_key
6. Ranks jobs based on configurable weights
7. Runs data quality tests
8. Publishes results to Tableau Hyper files
9. Sends webhook notification with summary

Schedule: Daily at 07:00 America/Toronto
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
import pendulum


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Timezone for scheduling (Toronto time)
TZ = pendulum.timezone("America/Toronto")

# Default arguments applied to all tasks
default_args = {
    "owner": "job-etl",
    "depends_on_past": False,  # Tasks don't depend on previous runs
    # start_date defined at DAG level for clarity
    "email_on_failure": False,  # Can enable later with email config
    "email_on_retry": False,
    "retries": 3,  # Retry failed tasks 3 times
    "retry_delay": timedelta(minutes=5),  # Wait 5 minutes between retries
    "retry_exponential_backoff": True,  # Increase delay exponentially
    "max_retry_delay": timedelta(minutes=30),  # Max 30 minute delay
}


# -----------------------------------------------------------------------------
# Task Callable Functions
# -----------------------------------------------------------------------------

def run_dbt_models(models: str, **context):
    """
    Run dbt models with the specified selection.

    Args:
        models: Model selection string (e.g., "stg_*", "dim_* fact_*")
    """
    import os
    import subprocess
    from airflow.hooks.base import BaseHook

    print("=" * 60)
    print(f"DBT TASK - Running models: {models}")
    print("=" * 60)

    try:
        # Get database credentials from Airflow connection
        try:
            conn = BaseHook.get_connection('postgres_default')
            db_host = conn.host
            db_port = conn.port
            db_user = conn.login
            db_password = conn.password
            db_name = conn.schema  # In Airflow connection, schema is the database name
            print("Using Airflow connection: postgres_default")
        except Exception as e:
            print(f"Warning: Could not get Airflow connection, trying environment variables: {e}")
            db_host = os.getenv('POSTGRES_HOST', 'postgres')
            db_port = os.getenv('POSTGRES_PORT', '5432')
            db_user = os.getenv('POSTGRES_USER', 'job_etl_user')
            db_password = os.getenv('POSTGRES_PASSWORD', 'secure_postgres_password_123')
            db_name = os.getenv('POSTGRES_DB', 'job_etl')

        # Set up dbt environment
        project_dir = '/opt/airflow/dbt/job_dbt'
        profiles_dir = '/tmp/dbt_profiles'
        target_path = '/tmp/dbt_target'
        log_path = '/tmp/dbt_logs'

        # Create temporary directories
        os.makedirs(profiles_dir, exist_ok=True)
        os.makedirs(target_path, exist_ok=True)
        os.makedirs(log_path, exist_ok=True)

        # Create profiles.yml
        profiles_yml = f"""job_dbt:
        target: docker
        outputs:
            docker:
                type: postgres
                host: {db_host}
                port: {db_port}
                user: {db_user}
                password: '{db_password}'
                dbname: {db_name}
                schema: staging
                threads: 4
                keepalives_idle: 0
                connect_timeout: 10
                search_path: "staging,raw,marts,public"
"""
        with open(f'{profiles_dir}/profiles.yml', 'w') as f:
            f.write(profiles_yml)

        # Run dbt command
        cmd = [
            'dbt',
            'run',
            '--models', models,
            '--project-dir', project_dir,
            '--profiles-dir', profiles_dir,
            '--target-path', target_path,
            '--log-path', log_path
        ]

        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)

        print("=" * 60)
        print(f"DBT TASK - Successfully ran models: {models}")
        print("=" * 60)

        return {"models_run": models, "status": "success"}

    except subprocess.CalledProcessError as e:
        print("=" * 60)
        print(f"DBT TASK - Failed with return code {e.returncode}")
        print("=" * 60)
        raise
    except Exception as e:
        print("=" * 60)
        print(f"DBT TASK - Unexpected error: {e}")
        print(f"Error type: {type(e).__name__}")
        print("=" * 60)
        raise


def run_core_dbt_models(**context):
    """Run core dbt models (dimensions and facts)."""
    return run_dbt_models(models="dim_* fact_*", **context)


def run_dbt_tests(**context):
    """
    Run dbt tests to validate data quality.

    Tests include:
    - Unique constraints on hash_key
    - Not null on critical fields
    - Accepted values for enums
    - Referential integrity (foreign keys)
    """
    import os
    import subprocess
    from airflow.hooks.base import BaseHook

    print("=" * 60)
    print("DBT TESTS TASK - Running data quality tests")
    print("=" * 60)

    try:
        # Get database credentials from Airflow connection
        try:
            conn = BaseHook.get_connection('postgres_default')
            db_host = conn.host
            db_port = conn.port
            db_user = conn.login
            db_password = conn.password
            db_name = conn.schema  # In Airflow connection, schema is the database name
            print("Using Airflow connection: postgres_default")
        except Exception as e:
            print(f"Warning: Could not get Airflow connection, trying environment variables: {e}")
            db_host = os.getenv('POSTGRES_HOST', 'postgres')
            db_port = os.getenv('POSTGRES_PORT', '5432')
            db_user = os.getenv('POSTGRES_USER', 'job_etl_user')
            db_password = os.getenv('POSTGRES_PASSWORD', 'secure_postgres_password_123')
            db_name = os.getenv('POSTGRES_DB', 'job_etl')

        # Set up dbt environment
        project_dir = '/opt/airflow/dbt/job_dbt'
        profiles_dir = '/tmp/dbt_profiles'
        target_path = '/tmp/dbt_target'
        log_path = '/tmp/dbt_logs'

        # Create temporary directories
        os.makedirs(profiles_dir, exist_ok=True)
        os.makedirs(target_path, exist_ok=True)
        os.makedirs(log_path, exist_ok=True)

        # Create profiles.yml
        profiles_yml = f"""job_dbt:
        target: docker
        outputs:
            docker:
                type: postgres
                host: {db_host}
                port: {db_port}
                user: {db_user}
                password: '{db_password}'
                dbname: {db_name}
                schema: staging
                threads: 4
                keepalives_idle: 0
                connect_timeout: 10
                search_path: "staging,raw,marts,public"
"""
        with open(f'{profiles_dir}/profiles.yml', 'w') as f:
            f.write(profiles_yml)

        # Run dbt test command
        cmd = [
            'dbt',
            'test',
            '--project-dir', project_dir,
            '--profiles-dir', profiles_dir,
            '--target-path', target_path,
            '--log-path', log_path
        ]

        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode != 0:
            print("=" * 60)
            print("DBT TESTS TASK - Some tests failed")
            print("=" * 60)
            raise subprocess.CalledProcessError(result.returncode, cmd)

        print("=" * 60)
        print("DBT TESTS TASK - All tests passed")
        print("=" * 60)

        return {"tests_status": "passed", "status": "success"}

    except subprocess.CalledProcessError as e:
        print("=" * 60)
        print(f"DBT TESTS TASK - Failed with return code {e.returncode}")
        print("=" * 60)
        raise
    except Exception as e:
        print("=" * 60)
        print(f"DBT TESTS TASK - Unexpected error: {e}")
        print(f"Error type: {type(e).__name__}")
        print("=" * 60)
        raise


def extract_source_jsearch(**context):
    """
    Extract job postings from JSearch API.

    This will:
    - Call the source-extractor service (via DockerOperator)
    - Pass API credentials from Airflow Variables/Connections
    - Store raw JSON to raw.job_postings_raw table
    - Return count of extracted jobs
    """
    import os
    import sys
    from typing import Optional
    from airflow.hooks.base import BaseHook

    # Ensure project root is on sys.path to import services
    project_root = '/opt/airflow'
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("=" * 60)
    print("EXTRACT TASK (JSearch API) - Starting")
    print("=" * 60)

    try:
        # Lazy imports after sys.path updated
        from services.source_extractor.adapters.jsearch_adapter import (
            JSearchAdapter,
        )
        from services.source_extractor.db_storage import JobStorage

        # Resolve database URL from Airflow connection with fallback to env
        try:
            conn = BaseHook.get_connection('postgres_default')
            database_url = conn.get_uri().replace('postgres://', 'postgresql://')
            print("Using Airflow connection: postgres_default")
        except Exception as e:
            print(f"Warning: Could not get Airflow connection, trying environment variables: {e}")
            # Try DATABASE_URL first
            database_url = os.getenv('DATABASE_URL')
            # If not set, build from individual components
            if not database_url:
                db_host = os.getenv('POSTGRES_HOST', 'postgres')
                db_port = os.getenv('POSTGRES_PORT', '5432')
                db_user = os.getenv('POSTGRES_USER', 'job_etl_user')
                db_password = os.getenv('POSTGRES_PASSWORD')
                db_name = os.getenv('POSTGRES_DB', 'job_etl')
                
                # Try to read password from secret file if available
                if not db_password:
                    secret_path = '/run/secrets/postgres_password'
                    if os.path.exists(secret_path):
                        try:
                            # Try UTF-8 first, then UTF-16 if that fails
                            with open(secret_path, 'r', encoding='utf-8') as f:
                                db_password = f.read().strip()
                        except UnicodeDecodeError:
                            # Fallback to UTF-16 (Windows might create files in UTF-16)
                            with open(secret_path, 'r', encoding='utf-16') as f:
                                db_password = f.read().strip()
                
                if db_password:
                    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                    print(f"Built DATABASE_URL from environment variables (host: {db_host})")
                else:
                    raise ValueError(
                        "DATABASE_URL must be configured via Airflow connection 'postgres_default' "
                        "or environment variables (DATABASE_URL or POSTGRES_*). "
                        "Also ensure postgres_password secret is mounted."
                    ) from None

        # Resolve API configuration from Airflow Variables with env fallbacks
        def _var(name: str, default: Optional[str] = None) -> Optional[str]:
            try:
                return Variable.get(name)
            except Exception:
                return os.getenv(name, default)

        jsearch_api_key = _var('JSEARCH_API_KEY')
        jsearch_base_url = _var('JSEARCH_BASE_URL', 'https://api.openwebninja.com')
        jsearch_query = _var('JSEARCH_QUERY', 'analytics engineer')
        jsearch_location = _var('JSEARCH_LOCATION', 'United States')
        jsearch_date_posted = _var('JSEARCH_DATE_POSTED', 'month')
        try:
            jsearch_max_jobs = int(_var('JSEARCH_MAX_JOBS', '20') or '20')
        except ValueError:
            jsearch_max_jobs = 20

        if not jsearch_api_key:
            raise ValueError(
                "JSEARCH_API_KEY must be set as an Airflow Variable or environment variable"
            )

        print("Initializing JSearch adapter with configuration:")
        print(f"  base_url: {jsearch_base_url}")
        print(f"  query: {jsearch_query}")
        print(f"  location: {jsearch_location}")
        print(f"  date_posted: {jsearch_date_posted}")
        print(f"  max_jobs: {jsearch_max_jobs}")

        adapter = JSearchAdapter(
            api_key=jsearch_api_key,
            base_url=jsearch_base_url,
            max_jobs=jsearch_max_jobs,
            query=jsearch_query,
            location=jsearch_location,
            date_posted=jsearch_date_posted,
        )

        total_saved = 0

        with JobStorage(database_url) as storage:
            next_token: Optional[str] = None
            while True:
                jobs, next_token = adapter.fetch(next_token)
                if not jobs:
                    break
                raw_ids = storage.save_jobs_batch(jobs)
                total_saved += len(raw_ids)
                print(f"Saved batch: {len(raw_ids)} (total_saved={total_saved})")
                if not next_token:
                    break

        print("=" * 60)
        print("EXTRACT TASK (JSearch API) - Completed Successfully")
        print("=" * 60)
        print(f"Extracted and saved jobs: {total_saved}")
        print("=" * 60)

        return {"source": "jsearch", "extracted_count": total_saved}

    except Exception as e:
        print("=" * 60)
        print("EXTRACT TASK (JSearch API) - Error")
        print("=" * 60)
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        print("=" * 60)
        raise


def normalize_data(**context):
    """
    Normalize raw data to canonical staging format.

    This function calls the normalizer service which:
    - Reads raw JSON from raw.job_postings_raw
    - Transforms provider-specific fields to our standard schema
    - Generates hash_key for deduplication
    - Upserts to staging.job_postings_stg (idempotent)
    - Returns count of normalized rows
    """
    import os
    import sys
    from airflow.hooks.base import BaseHook

    # Add project root to path so we can import services
    project_root = '/opt/airflow'
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("=" * 60)
    print("NORMALIZE TASK - Starting")
    print("=" * 60)

    try:
        # Import normalizer service
        from services.normalizer.db_operations import NormalizerDB, DatabaseError
        from services.normalizer.main import run_normalizer

        # Get database URL from Airflow connection with fallback to env
        try:
            conn = BaseHook.get_connection('postgres_default')
            database_url = conn.get_uri().replace('postgres://', 'postgresql://')
            print("Using Airflow connection: postgres_default")
        except Exception as e:
            print(f"Warning: Could not get Airflow connection, trying environment variables: {e}")
            # Try DATABASE_URL first
            database_url = os.getenv('DATABASE_URL')
            # If not set, build from individual components
            if not database_url:
                db_host = os.getenv('POSTGRES_HOST', 'postgres')
                db_port = os.getenv('POSTGRES_PORT', '5432')
                db_user = os.getenv('POSTGRES_USER', 'job_etl_user')
                db_password = os.getenv('POSTGRES_PASSWORD')
                db_name = os.getenv('POSTGRES_DB', 'job_etl')
                
                # Try to read password from secret file if available
                if not db_password:
                    secret_path = '/run/secrets/postgres_password'
                    if os.path.exists(secret_path):
                        try:
                            # Try UTF-8 first, then UTF-16 if that fails
                            with open(secret_path, 'r', encoding='utf-8') as f:
                                db_password = f.read().strip()
                        except UnicodeDecodeError:
                            # Fallback to UTF-16 (Windows might create files in UTF-16)
                            with open(secret_path, 'r', encoding='utf-16') as f:
                                db_password = f.read().strip()
                
                if db_password:
                    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                    print(f"Built DATABASE_URL from environment variables (host: {db_host})")
                else:
                    raise ValueError(
                        "DATABASE_URL must be configured via Airflow connection 'postgres_default' "
                        "or environment variables (DATABASE_URL or POSTGRES_*). "
                        "Also ensure postgres_password secret is mounted."
                    ) from None

        print("Connecting to database...")

        # Initialize database connection
        db = NormalizerDB(database_url)

        # Run normalizer service
        # Filter by source if provided via XCom from extract task
        ti = context['ti']
        extract_result = ti.xcom_pull(task_ids='extract_jsearch')
        source_filter = extract_result.get('source') if extract_result else 'jsearch'

        print(f"Normalizing jobs from source: {source_filter}")

        stats = run_normalizer(
            db=db,
            source=source_filter,
            limit=None,  # Process all available raw jobs
            min_collected_at=None,  # Process all timestamps
            dry_run=False
        )

        print("=" * 60)
        print("NORMALIZE TASK - Completed Successfully")
        print("=" * 60)
        print("Results:")
        print(f"  - Fetched: {stats['fetched']}")
        print(f"  - Normalized: {stats['normalized']}")
        print(f"  - Upserted: {stats['upserted']}")
        print(f"  - Failed: {stats['failed']}")
        print(f"  - Skipped: {stats['skipped']}")
        print("=" * 60)

        # Return stats for downstream tasks via XCom
        return {
            "normalized_count": stats['normalized'],
            "upserted_count": stats['upserted'],
            "failed_count": stats['failed'],
            "source": source_filter
        }

    except DatabaseError as e:
        print("=" * 60)
        print("NORMALIZE TASK - Database Error")
        print("=" * 60)
        print(f"Error: {e}")
        print("=" * 60)
        raise

    except Exception as e:
        print("=" * 60)
        print("NORMALIZE TASK - Unexpected Error")
        print("=" * 60)
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        print("=" * 60)
        raise


def enrich_data(**context):
    """
    Enrich job postings with skills, standardized titles, locations, etc.

    For now, this is a no-op placeholder. In the next phase, this will:
    - Call the enricher service (via DockerOperator)
    - Extract skills using NLP
    - Standardize job titles via taxonomy
    - Normalize locations and salaries
    - Update staging tables with enriched data
    """
    print("=" * 60)
    print("ENRICH TASK")
    print("=" * 60)
    print("TODO: Implement enrichment")
    print("  - Will call enricher service")
    print("  - Extract skills, standardize titles")
    print("  - Normalize locations and salaries")
    print("=" * 60)

    return {"enriched_count": 0}


def rank_jobs(**context):
    """
    Rank jobs based on configurable weights and profile.

    This function:
    - Calls the ranker service
    - Reads config/ranking.yml for weights and profile
    - Calculates rank_score (0-100) for each job
    - Generates rank_explain JSON with per-feature subscores
    - Updates marts.fact_jobs with scores
    """
    import os
    import sys
    from airflow.hooks.base import BaseHook

    # Add project root to path so we can import services
    project_root = '/opt/airflow'
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("=" * 60)
    print("RANK TASK - Starting")
    print("=" * 60)

    try:
        # Import ranker service
        from services.ranker.db_operations import RankerDB
        from services.ranker.config_loader import load_ranking_config
        from services.ranker.scoring import calculate_rank

        # Get database URL from Airflow connection with fallback to env
        try:
            conn = BaseHook.get_connection('postgres_default')
            database_url = conn.get_uri().replace('postgres://', 'postgresql://')
            print("Using Airflow connection: postgres_default")
        except Exception as e:
            print(f"Warning: Could not get Airflow connection, trying environment variables: {e}")
            # Try DATABASE_URL first
            database_url = os.getenv('DATABASE_URL')
            # If not set, build from individual components
            if not database_url:
                db_host = os.getenv('POSTGRES_HOST', 'postgres')
                db_port = os.getenv('POSTGRES_PORT', '5432')
                db_user = os.getenv('POSTGRES_USER', 'job_etl_user')
                db_password = os.getenv('POSTGRES_PASSWORD')
                db_name = os.getenv('POSTGRES_DB', 'job_etl')
                
                # Try to read password from secret file if available
                if not db_password:
                    secret_path = '/run/secrets/postgres_password'
                    if os.path.exists(secret_path):
                        try:
                            # Try UTF-8 first, then UTF-16 if that fails
                            with open(secret_path, 'r', encoding='utf-8') as f:
                                db_password = f.read().strip()
                        except UnicodeDecodeError:
                            # Fallback to UTF-16 (Windows might create files in UTF-16)
                            with open(secret_path, 'r', encoding='utf-16') as f:
                                db_password = f.read().strip()
                
                if db_password:
                    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                    print(f"Built DATABASE_URL from environment variables (host: {db_host})")
                else:
                    raise ValueError(
                        "DATABASE_URL must be configured via Airflow connection 'postgres_default' "
                        "or environment variables (DATABASE_URL or POSTGRES_*). "
                        "Also ensure postgres_password secret is mounted."
                    ) from None

        print("Loading ranking configuration...")
        config = load_ranking_config()

        print("Connecting to database...")
        db = RankerDB(database_url)

        print("Fetching unranked jobs...")
        jobs = db.fetch_unranked_jobs(limit=None)

        if not jobs:
            print("No unranked jobs found")
            return {"ranked_count": 0, "total_count": 0}

        print(f"Found {len(jobs)} jobs to rank")

        # Rank each job
        rankings = []
        for i, job in enumerate(jobs, 1):
            try:
                rank_score, rank_explain = calculate_rank(job, config)
                rankings.append({
                    'hash_key': job['hash_key'],
                    'rank_score': rank_score,
                    'rank_explain': rank_explain,
                })

                if i % 10 == 0 or i == len(jobs):
                    print(f"  Ranked {i}/{len(jobs)} jobs...")

            except Exception as e:
                print(f"  Warning: Failed to rank job {job.get('hash_key', 'unknown')}: {e}")
                continue

        # Update database
        print(f"Updating database with {len(rankings)} rankings...")
        updated_count = db.update_jobs_ranking_batch(rankings)

        # Get overall statistics
        stats = db.get_ranking_stats()

        print("=" * 60)
        print("RANK TASK - Completed Successfully")
        print("=" * 60)
        print("Results:")
        print(f"  - Total jobs found:   {stats['total_jobs']}")
        print(f"  - Previously ranked:  {stats['ranked_jobs'] - len(rankings)}")
        print(f"  - Newly ranked:       {updated_count}")
        print(f"  - Total ranked:       {stats['ranked_jobs']}")
        print(f"  - Unranked:           {stats['unranked_jobs']}")
        if stats['average_score']:
            print(f"  - Average score:      {stats['average_score']:.2f}")
            print(f"  - Top score:          {stats['top_score']:.2f}")
        print("=" * 60)

        return {
            "ranked_count": updated_count,
            "total_count": stats['total_jobs'],
            "average_score": stats['average_score'],
            "top_score": stats['top_score']
        }

    except Exception as e:
        print("=" * 60)
        print("RANK TASK - Error")
        print("=" * 60)
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        print("=" * 60)
        raise


def publish_to_tableau(**context):
    """
    Publish ranked jobs to Tableau Hyper files.

    For now, this is a no-op placeholder. In the next phase, this will:
    - Call the publisher-hyper service (via DockerOperator)
    - Export marts.fact_jobs and marts.dim_companies
    - Create .hyper files in ./artifacts/
    - Optionally publish to Tableau Server/Cloud
    """
    print("=" * 60)
    print("PUBLISH TASK")
    print("=" * 60)
    try:
        # Lazy import to avoid heavy deps unless this task runs
        from services.publisher_hyper.exporter import export_from_env
        hyper_path = export_from_env(output_dir="artifacts", hyper_filename="jobs_ranked.hyper")
        print(f"Created hyper: {hyper_path}")
        print("=" * 60)
        return {"hyper_file": hyper_path}
    except Exception as e:
        print("Publish failed:", e)
        print("=" * 60)
        # Still return a value for downstream tasks
        return {"hyper_file": None, "error": str(e)}


def send_webhook_notification(**context):
    """
    Send daily summary to configured webhook (Slack/Discord).

    This function:
    - Collects counts from XCom (extracted, staged, ranked)
    - Queries database for top ranked jobs
    - Reads webhook URL from Airflow Variables/environment
    - Formats summary JSON with top matches and failures
    - POSTs to webhook endpoint
    """
    import os
    import sys
    import json
    import requests
    from datetime import datetime, timezone
    from typing import Optional
    from airflow.hooks.base import BaseHook
    from airflow.models import TaskInstance

    # Add project root to path so we can import services
    project_root = '/opt/airflow'
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("=" * 60)
    print("WEBHOOK NOTIFICATION TASK - Starting")
    print("=" * 60)

    try:
        # Get task instance and DAG run from context
        ti: TaskInstance = context['ti']
        dag_run = context['dag_run']

        # Calculate duration
        start_time = dag_run.start_date
        if start_time and start_time.tzinfo:
            end_time = datetime.now(start_time.tzinfo)
        else:
            end_time = datetime.now(timezone.utc)
        duration_sec = int((end_time - start_time).total_seconds()) if start_time else 0

        # Determine overall status
        dag_state = dag_run.state
        is_success = dag_state == 'success'

        # Collect counts from XCom
        extract_result = ti.xcom_pull(task_ids='extract_jsearch', default={})
        normalize_result = ti.xcom_pull(task_ids='normalize', default={})
        enrich_result = ti.xcom_pull(task_ids='enrich', default={})
        rank_result = ti.xcom_pull(task_ids='rank', default={})

        extracted_count = extract_result.get('extracted_count', 0)
        normalized_count = normalize_result.get('normalized_count', 0)
        enriched_count = enrich_result.get('enriched_count', 0)
        ranked_count = rank_result.get('ranked_count', 0)

        # Get database connection for queries
        try:
            conn = BaseHook.get_connection('postgres_default')
            database_url = conn.get_uri().replace('postgres://', 'postgresql://')
            print("Using Airflow connection: postgres_default")
        except Exception as e:
            print(f"Warning: Could not get Airflow connection, trying environment variable: {e}")
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                print("Warning: DATABASE_URL not configured, skipping database queries")
                database_url = None

        # Query top ranked jobs and get counts
        top_matches = []
        deduped_unique_count = 0

        if database_url:
            try:
                import psycopg2
                import psycopg2.extras

                with psycopg2.connect(database_url) as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        # Get total unique jobs (deduped)
                        cur.execute("""
                            SELECT COUNT(DISTINCT hash_key) as count
                            FROM marts.fact_jobs
                        """)
                        deduped_unique_count = cur.fetchone()['count'] or 0

                        # Get total ranked jobs (for potential future use)
                        # Currently not used in payload, but kept for completeness
                        cur.execute("""
                            SELECT COUNT(*) as count
                            FROM marts.fact_jobs
                            WHERE rank_score IS NOT NULL
                        """)
                        # Note: total_ranked not used in current payload, but query kept for stats
                        _ = cur.fetchone()['count'] or 0

                        # Get top 25 ranked jobs from this run
                        # Filter for jobs ingested since the DAG execution date
                        # This ensures we only show new matches from the current run
                        execution_date = dag_run.execution_date
                        if execution_date:
                            # Filter for jobs ingested since the execution date (start of this run)
                            # Use a small buffer (1 hour before) to account for any timing edge cases
                            filter_time = execution_date - timedelta(hours=1)
                            print(f"Filtering top matches for jobs ingested since: {filter_time}")
                            cur.execute("""
                                SELECT
                                    f.job_title_std as title,
                                    d.company,
                                    f.location_std as location,
                                    f.rank_score as score,
                                    f.apply_url
                                FROM marts.fact_jobs f
                                LEFT JOIN marts.dim_companies d ON f.company_id = d.company_id
                                WHERE f.rank_score IS NOT NULL
                                  AND f.ingested_at >= %s
                                ORDER BY f.rank_score DESC, f.ingested_at DESC
                                LIMIT 25
                            """, (filter_time,))
                        else:
                            # Fallback: if no execution_date, use last 24 hours from start_date
                            if dag_run.start_date:
                                filter_time = dag_run.start_date - timedelta(hours=24)
                                print(f"Using fallback: filtering top matches for jobs ingested since: {filter_time} (24h before start_date)")
                                cur.execute("""
                                    SELECT
                                        f.job_title_std as title,
                                        d.company,
                                        f.location_std as location,
                                        f.rank_score as score,
                                        f.apply_url
                                    FROM marts.fact_jobs f
                                    LEFT JOIN marts.dim_companies d ON f.company_id = d.company_id
                                    WHERE f.rank_score IS NOT NULL
                                      AND f.ingested_at >= %s
                                    ORDER BY f.rank_score DESC, f.ingested_at DESC
                                    LIMIT 25
                                """, (filter_time,))
                            else:
                                # Last resort: get top 25 without time filter
                                print("Warning: No execution_date or start_date available, fetching top 25 without time filter")
                                cur.execute("""
                                    SELECT
                                        f.job_title_std as title,
                                        d.company,
                                        f.location_std as location,
                                        f.rank_score as score,
                                        f.apply_url
                                    FROM marts.fact_jobs f
                                    LEFT JOIN marts.dim_companies d ON f.company_id = d.company_id
                                    WHERE f.rank_score IS NOT NULL
                                    ORDER BY f.rank_score DESC, f.ingested_at DESC
                                    LIMIT 25
                                """)
                        top_jobs = cur.fetchall()

                        for job in top_jobs:
                            top_matches.append({
                                "title": job['title'] or 'Unknown',
                                "company": job['company'] or 'Unknown',
                                "location": job['location'] or 'Unknown',
                                "score": float(job['score']) if job['score'] else 0.0,
                                "apply_url": job['apply_url'] or ''
                            })

            except Exception as e:
                print(f"Warning: Failed to query database for top matches: {e}")
                print("Continuing with webhook notification without database data")

        # Collect failed tasks
        failed_tasks = []
        if not is_success:
            # Check all tasks in the DAG run
            for task_instance in dag_run.get_task_instances():
                if task_instance.state == 'failed':
                    failed_tasks.append(task_instance.task_id)

        # Build webhook payload
        payload = {
            "run_id": dag_run.run_id,
            "status": "success" if is_success else "failed",
            "counts": {
                "extracted": extracted_count,
                "staged": normalized_count,
                "deduped_unique": deduped_unique_count,
                "enriched": enriched_count,
                "ranked": ranked_count,
                "top_matches": len(top_matches)
            },
            "new_top_matches": top_matches,
            "failures": failed_tasks,
            "duration_sec": duration_sec
        }

        # Get webhook URL from Airflow Variables or environment
        def _get_webhook_url() -> Optional[str]:
            try:
                return Variable.get('WEBHOOK_URL')
            except Exception:
                return os.getenv('WEBHOOK_URL')

        webhook_url = _get_webhook_url()

        if not webhook_url:
            print("=" * 60)
            print("WEBHOOK NOTIFICATION TASK - Skipped (no webhook URL configured)")
            print("=" * 60)
            print("To enable webhook notifications, set WEBHOOK_URL as:")
            print("  - Airflow Variable: WEBHOOK_URL")
            print("  - Environment variable: WEBHOOK_URL")
            print("=" * 60)
            print("Payload that would have been sent:")
            print(json.dumps(payload, indent=2))
            print("=" * 60)
            return {"notification_sent": False, "reason": "no_webhook_url", "payload": payload}

        # Send webhook notification
        try:
            print(f"Sending webhook notification to: {webhook_url}")
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30  # 30 second timeout
            )
            response.raise_for_status()  # Raise exception for bad status codes

            print("=" * 60)
            print("WEBHOOK NOTIFICATION TASK - Success")
            print("=" * 60)
            print(f"Response status: {response.status_code}")
            print(f"Payload sent: {json.dumps(payload, indent=2)}")
            print("=" * 60)

            return {
                "notification_sent": True,
                "status_code": response.status_code,
                "payload": payload
            }

        except requests.exceptions.RequestException as e:
            print("=" * 60)
            print("WEBHOOK NOTIFICATION TASK - Failed to send webhook")
            print("=" * 60)
            print(f"Error: {e}")
            print("Payload that failed to send:")
            print(json.dumps(payload, indent=2))
            print("=" * 60)
            # Don't raise - we don't want webhook failures to fail the DAG
            return {
                "notification_sent": False,
                "error": str(e),
                "payload": payload
            }

    except Exception as e:
        print("=" * 60)
        print("WEBHOOK NOTIFICATION TASK - Unexpected Error")
        print("=" * 60)
        print(f"Error: {e}")
        print(f"Error type: {type(e).__name__}")
        print("=" * 60)
        # Don't raise - we don't want webhook failures to fail the DAG
        return {"notification_sent": False, "error": str(e)}


# -----------------------------------------------------------------------------
# DAG Definition
# -----------------------------------------------------------------------------

with DAG(
    dag_id="jobs_etl_daily",
    default_args=default_args,
    description="Daily ETL pipeline for job postings with ranking and Tableau export",
    schedule_interval="0 7 * * *",  # Daily at 07:00 (cron format)
    start_date=datetime(2025, 10, 1, tzinfo=TZ),
    catchup=False,  # Don't backfill for past dates
    max_active_runs=1,  # Only one run at a time
    tags=["etl", "jobs", "daily", "production"],
) as dag:

    # -------------------------------------------------------------------------
    # Task 1: Start (Dummy marker)
    # -------------------------------------------------------------------------
    start = DummyOperator(
        task_id="start",
        doc_md="""
        **Start of jobs_etl_daily pipeline**

        This is a dummy task that marks the beginning of the DAG.
        It has no functionality but helps visualize the flow in the UI.
        """
    )

    # -------------------------------------------------------------------------
    # Task 2: Extract from JSearch API
    # -------------------------------------------------------------------------
    extract_jsearch = PythonOperator(
        task_id="extract_jsearch",
        python_callable=extract_source_jsearch,
        retries=3,  # Retry API calls up to 3 times
        doc_md="""
        **Extract job postings from JSearch API**

        - Calls source-extractor service with JSearch adapter
        - Stores raw JSON to raw.job_postings_raw
        - Returns extracted count via XCom
        """
    )

    # -------------------------------------------------------------------------
    # Task 3: Normalize data
    # -------------------------------------------------------------------------
    normalize = PythonOperator(
        task_id="normalize",
        python_callable=normalize_data,
        retries=3,
        doc_md="""
        **Normalize data to canonical format**

        - Calls normalizer service
        - Converts provider-specific fields to standard schema
        - Ensures consistent enums and data types
        """
    )

    # -------------------------------------------------------------------------
    # Task 5: Enrich data
    # -------------------------------------------------------------------------
    enrich = PythonOperator(
        task_id="enrich",
        python_callable=enrich_data,
        retries=3,
        doc_md="""
        **Enrich job postings**

        - Extract skills using NLP (spaCy + keyword lists)
        - Standardize job titles via taxonomy
        - Normalize locations and salaries to CAD
        - Map company sizes to standard bins
        """
    )

    # -------------------------------------------------------------------------
    # Task 6: Run core dbt models (intermediate, dimensions, facts)
    # -------------------------------------------------------------------------
    dbt_models_core = PythonOperator(
        task_id="dbt_models_core",
        python_callable=run_core_dbt_models,
        retries=2,
        doc_md="""
        **dbt: Build core models**

        - Runs intermediate models (int_*)
        - Builds dimension tables (dim_companies)
        - Builds fact tables (fact_jobs)
        - Generates surrogate keys and relationships
        """
    )

    # -------------------------------------------------------------------------
    # Task 7: Deduplicate and consolidate
    # -------------------------------------------------------------------------
    dedupe_consolidate = BashOperator(
        task_id="dedupe_consolidate",
        bash_command="""
        echo "Running deduplication logic..."
        echo "TODO: Run incremental dbt model or SQL for deduplication"
        echo "Uses hash_key = md5(lower(company)||'|'||lower(title)||'|'||lower(location))"
        echo "Updates last_seen_at, preserves first_seen_at"
        """,
        retries=2,
        doc_md="""
        **Deduplicate job postings**

        - Uses hash_key = md5(company|title|location)
        - Upserts: update last_seen_at if exists, insert if new
        - Preserves first_seen_at for historical tracking
        """
    )

    # -------------------------------------------------------------------------
    # Task 8: Rank jobs
    # -------------------------------------------------------------------------
    rank = PythonOperator(
        task_id="rank",
        python_callable=rank_jobs,
        retries=3,
        doc_md="""
        **Rank job postings**

        - Calls ranker service
        - Reads config/ranking.yml for weights and profile
        - Calculates rank_score (0-100)
        - Generates rank_explain JSON with feature subscores
        - Updates marts.fact_jobs
        """
    )

    # -------------------------------------------------------------------------
    # Task 9: Run dbt tests
    # -------------------------------------------------------------------------
    dbt_tests = PythonOperator(
        task_id="dbt_tests",
        python_callable=run_dbt_tests,
        retries=1,
        doc_md="""
        **dbt: Data quality tests**

        - Tests unique constraints on hash_key
        - Tests not_null on critical fields
        - Tests accepted_values for enums
        - Tests referential integrity (foreign keys)
        """
    )

    # -------------------------------------------------------------------------
    # Task 10: Publish to Tableau Hyper
    # -------------------------------------------------------------------------
    publish_hyper = PythonOperator(
        task_id="publish_hyper",
        python_callable=publish_to_tableau,
        retries=2,
        doc_md="""
        **Publish to Tableau**

        - Calls publisher-hyper service
        - Exports marts.fact_jobs and marts.dim_companies
        - Creates .hyper files in ./artifacts/
        - Optionally publishes to Tableau Server/Cloud
        """
    )

    # -------------------------------------------------------------------------
    # Task 11: Send webhook notification
    # -------------------------------------------------------------------------
    notify_webhook_daily = PythonOperator(
        task_id="notify_webhook_daily",
        python_callable=send_webhook_notification,
        retries=2,
        trigger_rule="all_done",  # Run even if upstream tasks fail
        doc_md="""
        **Send daily summary webhook**

        - Collects counts from all tasks (extracted, staged, ranked)
        - Formats summary JSON with top matches
        - POSTs to configured Slack/Discord webhook
        - Runs even if upstream tasks fail (to report errors)
        """
    )

    # -------------------------------------------------------------------------
    # Task 12: End (Dummy marker)
    # -------------------------------------------------------------------------
    end = DummyOperator(
        task_id="end",
        doc_md="""
        **End of jobs_etl_daily pipeline**

        This is a dummy task that marks the successful completion of the DAG.
        """
    )

    # -------------------------------------------------------------------------
    # Task Dependencies (Define the execution order)
    # -------------------------------------------------------------------------

    # Linear flow: start → extract → normalize → enrich → models → dedupe → rank → tests → publish → notify → end
    start >> extract_jsearch
    extract_jsearch >> normalize
    normalize >> enrich
    enrich >> dbt_models_core
    dbt_models_core >> dedupe_consolidate
    dedupe_consolidate >> rank
    rank >> dbt_tests
    dbt_tests >> publish_hyper
    publish_hyper >> notify_webhook_daily
    notify_webhook_daily >> end

