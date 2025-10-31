"""
Job-ETL Daily DAG

This DAG orchestrates the daily ETL pipeline for job postings:
1. Extracts job data from configured sources (JSearch API)
2. Loads raw data to staging via dbt
3. Normalizes data to canonical format
4. Enriches with skills, standardized titles, locations, salary
5. Runs core dbt models (dimensions and facts)
6. Deduplicates based on hash_key
7. Ranks jobs based on configurable weights
8. Runs data quality tests
9. Publishes results to Tableau Hyper files
10. Sends webhook notification with summary

Schedule: Daily at 07:00 America/Toronto
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
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
# Task Callable Functions (Placeholders for now)
# -----------------------------------------------------------------------------

def extract_source_jsearch(**context):
    """
    Extract job postings from JSearch API.

    For now, this is a no-op placeholder. In the next phase, this will:
    - Call the source-extractor service (via DockerOperator)
    - Pass API credentials from Airflow Variables/Connections
    - Store raw JSON to raw.job_postings_raw table
    - Return count of extracted jobs
    """
    print("=" * 60)
    print("EXTRACT TASK (JSearch API)")
    print("=" * 60)
    print("TODO: Implement source extraction")
    print("  - Will call source-extractor service")
    print("  - Store raw JSON to raw.job_postings_raw")
    print("  - Return job count for XCom")
    print("=" * 60)

    # Placeholder return value (will be replaced with actual count)
    return {"source": "jsearch", "extracted_count": 0}


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
        
        # Get database URL from Airflow connection
        try:
            conn = BaseHook.get_connection('postgres_default')
            database_url = conn.get_uri().replace('postgres://', 'postgresql://')
            print("Using Airflow connection: postgres_default")
        except Exception as e:
            print(f"Warning: Could not get Airflow connection, using fallback: {e}")
            database_url = os.getenv(
                'DATABASE_URL',
                'postgresql://job_etl_user:job_etl_pass@postgres:5432/job_etl'
            )
        
        print(f"Connecting to database...")
        
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
        print(f"Results:")
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

    For now, this is a no-op placeholder. In the next phase, this will:
    - Call the ranker service (via DockerOperator)
    - Read config/ranking.yml for weights
    - Calculate rank_score (0-100)
    - Generate rank_explain JSON
    - Update marts.fact_jobs with scores
    """
    print("=" * 60)
    print("RANK TASK")
    print("=" * 60)
    print("TODO: Implement ranking")
    print("  - Will call ranker service")
    print("  - Calculate rank_score with explainability")
    print("  - Update marts.fact_jobs")
    print("=" * 60)

    return {"ranked_count": 0}


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
    print("TODO: Implement Tableau export")
    print("  - Will call publisher-hyper service")
    print("  - Create .hyper files in ./artifacts/")
    print("=" * 60)

    return {"hyper_file": "artifacts/jobs_ranked_PLACEHOLDER.hyper"}


def send_webhook_notification(**context):
    """
    Send daily summary to configured webhook (Slack/Discord).

    For now, this is a no-op placeholder. In the next phase, this will:
    - Collect counts from XCom (extracted, staged, ranked)
    - Read webhook URL from Airflow Variables/Connections
    - Format summary JSON with top matches
    - POST to webhook endpoint
    """
    print("=" * 60)
    print("WEBHOOK NOTIFICATION TASK")
    print("=" * 60)
    print("TODO: Implement webhook notification")
    print("  - Collect counts from upstream tasks")
    print("  - Format summary with top matches")
    print("  - POST to configured webhook URL")
    print("=" * 60)

    return {"notification_sent": False}


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
    # Task 3: Load raw data to staging (dbt)
    # -------------------------------------------------------------------------
    load_raw_to_staging = BashOperator(
        task_id="load_raw_to_staging",
        bash_command="""
        echo "Running dbt staging models..."
        echo "TODO: cd /opt/airflow/dbt/job_dbt && dbt run --models stg_*"
        echo "This will transform raw.job_postings_raw to staging.job_postings_stg"
        """,
        retries=2,
        doc_md="""
        **dbt: Load raw data to staging**

        - Runs dbt models: stg_job_postings
        - Transforms raw JSON to typed, cleaned staging tables
        - Applies enums, trims whitespace, normalizes nulls
        """
    )

    # -------------------------------------------------------------------------
    # Task 4: Normalize data
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
    dbt_models_core = BashOperator(
        task_id="dbt_models_core",
        bash_command="""
        echo "Running dbt core models..."
        echo "TODO: cd /opt/airflow/dbt/job_dbt && dbt run --models int_* dim_* fact_*"
        echo "This will create marts.dim_companies and marts.fact_jobs"
        """,
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
    dbt_tests = BashOperator(
        task_id="dbt_tests",
        bash_command="""
        echo "Running dbt tests..."
        echo "TODO: cd /opt/airflow/dbt/job_dbt && dbt test"
        echo "Tests: unique hash_key, not_null, accepted_values, relationships"
        """,
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

    # Linear flow: start â†’ extract â†’ load â†’ normalize â†’ enrich â†’ models â†’ dedupe â†’ rank â†’ tests â†’ publish â†’ notify â†’ end
    start >> extract_jsearch
    extract_jsearch >> load_raw_to_staging
    load_raw_to_staging >> normalize
    normalize >> enrich
    enrich >> dbt_models_core
    dbt_models_core >> dedupe_consolidate
    dedupe_consolidate >> rank
    rank >> dbt_tests
    dbt_tests >> publish_hyper
    publish_hyper >> notify_webhook_daily
    notify_webhook_daily >> end

