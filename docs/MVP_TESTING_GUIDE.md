# MVP Testing Guide - Complete End-to-End Flow

This guide walks you through testing the complete MVP ETL pipeline from start to finish.

## Prerequisites

1. Docker and Docker Compose installed
2. Git repository cloned
3. Environment configured (see setup steps below)

## Step 1: Environment Setup

### 1.1 Create Environment File

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (if needed)
# Default values should work for local testing
```

### 1.2 Create Secret Files

```bash
# Create secrets directory structure
mkdir -p secrets/database
mkdir -p secrets/airflow

# Generate database password (or use a simple one for testing)
echo "test_password_123" > secrets/database/postgres_password.txt

# Generate Airflow PostgreSQL password
echo "airflow_test_123" > secrets/airflow/airflow_postgres_password.txt

# Set permissions (Linux/Mac)
chmod 600 secrets/database/postgres_password.txt
chmod 600 secrets/airflow/airflow_postgres_password.txt
```

### 1.3 Set Up JSearch API Key

You need a JSearch API key from OpenWebNinja (or similar provider):

**Option A: Via Airflow UI (Recommended)**
1. Start Airflow: `docker-compose up -d`
2. Open http://localhost:8080
3. Go to Admin → Variables
4. Add variable: `JSEARCH_API_KEY` with your API key value

**Option B: Via Environment Variable**
Add to your `.env` file:
```bash
JSEARCH_API_KEY=your_api_key_here
```

### 1.4 Set Up Webhook URL (Optional)

If you want to test webhook notifications:

**Option A: Via Airflow UI**
1. Go to Admin → Variables
2. Add variable: `WEBHOOK_URL` with your webhook URL (e.g., Slack/Discord webhook)

**Option B: Via Environment Variable**
Add to your `.env` file:
```bash
WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Note:** If not configured, the webhook task will log a warning and show what would have been sent.

## Step 2: Start Services

### 2.1 Initialize Database and Airflow

```bash
# Start database services first
docker-compose up -d postgres airflow-postgres redis

# Wait for databases to be ready (about 30 seconds)
docker-compose ps

# Initialize Airflow (creates admin user and connections)
docker-compose run --rm airflow-init
```

### 2.2 Start All Services

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs if needed
docker-compose logs -f airflow-scheduler
```

## Step 3: Verify Setup

### 3.1 Check Airflow UI

1. Open browser: http://localhost:8080
2. Login:
   - Username: `admin`
   - Password: `admin` (or value from `.env` `AIRFLOW_ADMIN_PASSWORD`)
3. Verify DAG appears:
   - Look for `jobs_etl_daily` DAG in the list
   - Status should show as "Active" (green circle)

### 3.2 Verify Database Connection

```bash
# Connect to database
docker-compose exec postgres psql -U job_etl_user -d job_etl

# Check schemas exist
\dn

# Should show: raw, staging, marts

# Check tables exist
\dt raw.*
\dt staging.*
\dt marts.*

# Exit
\q
```

### 3.3 Verify Airflow Connection

In Airflow UI:
1. Go to Admin → Connections
2. Verify `postgres_default` connection exists
3. Test connection if available

## Step 4: Configure Airflow Variables

### 4.1 Required Variables

Go to Admin → Variables in Airflow UI and add:

| Variable Name | Description | Example |
|--------------|-------------|---------|
| `JSEARCH_API_KEY` | API key for JSearch/OpenWebNinja | `your_api_key_here` |
| `JSEARCH_BASE_URL` | (Optional) Base URL for API | `https://api.openwebninja.com` |
| `JSEARCH_QUERY` | (Optional) Search query | `analytics engineer` |
| `JSEARCH_LOCATION` | (Optional) Location filter | `United States` |
| `JSEARCH_MAX_JOBS` | (Optional) Max jobs to fetch | `20` |
| `WEBHOOK_URL` | (Optional) Webhook URL for notifications | `https://hooks.slack.com/...` |

### 4.2 Verify Variables

```bash
# List variables via CLI
docker-compose exec airflow-webserver airflow variables list
```

## Step 5: Run the Complete ETL Pipeline

### 5.1 Trigger the DAG

**Option A: Via Airflow UI (Recommended)**
1. Open DAG: `jobs_etl_daily`
2. Click "Play" button (▶) to trigger the DAG
3. Monitor progress in the Graph View

**Option B: Via CLI**
```bash
# Unpause the DAG (if paused)
docker-compose exec airflow-webserver airflow dags unpause jobs_etl_daily

# Trigger the DAG
docker-compose exec airflow-webserver airflow dags trigger jobs_etl_daily
```

### 5.2 Monitor Execution

**In Airflow UI:**
1. Click on the DAG run
2. View Graph View to see task progress
3. Click on individual tasks to see logs

**Via CLI:**
```bash
# View DAG runs
docker-compose exec airflow-webserver airflow dags list-runs -d jobs_etl_daily

# View task logs
docker-compose exec airflow-webserver airflow tasks logs jobs_etl_daily extract_jsearch 2025-01-27
```

## Step 6: Verify Data Flow

### 6.1 Check Raw Data

```bash
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT COUNT(*) as raw_count, source, MIN(collected_at) as first_job, MAX(collected_at) as last_job
FROM raw.job_postings_raw
GROUP BY source;
"
```

**Expected:** Should show jobs from `jsearch` source.

### 6.2 Check Staging Data

```bash
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT COUNT(*) as staged_count, 
       COUNT(DISTINCT hash_key) as unique_jobs,
       MIN(first_seen_at) as first_seen,
       MAX(last_seen_at) as last_seen
FROM staging.job_postings_stg;
"
```

**Expected:** Should show normalized jobs with unique hash_keys.

### 6.3 Check Marts Data

```bash
# Check companies
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT COUNT(*) as company_count FROM marts.dim_companies;
"

# Check jobs with rankings
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT 
    COUNT(*) as total_jobs,
    COUNT(rank_score) as ranked_jobs,
    AVG(rank_score) as avg_score,
    MAX(rank_score) as top_score
FROM marts.fact_jobs;
"
```

**Expected:** Should show jobs with rankings populated.

### 6.4 Check Tableau Hyper Export

```bash
# Check if hyper file was created
ls -lh artifacts/*.hyper

# Or check in Airflow logs
docker-compose exec airflow-webserver airflow tasks logs jobs_etl_daily publish_hyper <run_id>
```

**Expected:** `jobs_ranked.hyper` file should exist in `artifacts/` directory.

## Step 7: Verify Tests Pass

### 7.1 Check dbt Tests

In Airflow UI, check the `dbt_tests` task:
- Should show "Success" (green)
- Logs should show all tests passing

Or check via database:
```bash
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
-- Test unique constraint
SELECT hash_key, COUNT(*) as count
FROM marts.fact_jobs
GROUP BY hash_key
HAVING COUNT(*) > 1;
"
```

**Expected:** Should return 0 rows (all hash_keys are unique).

### 7.2 Check Webhook Notification

If webhook URL is configured:
- Check your Slack/Discord channel for notification
- Should show summary with counts and top matches

If not configured:
- Check Airflow logs for `notify_webhook_daily` task
- Should show warning and payload that would have been sent

## Step 8: Verify Complete Flow

### 8.1 Expected Task Sequence

The DAG should execute in this order:
1. ✅ `start` - Dummy task
2. ✅ `extract_jsearch` - Extracts jobs from API
3. ✅ `normalize` - Normalizes to staging format
4. ✅ `enrich` - Enriches data (placeholder for Phase 1)
5. ✅ `dbt_models_core` - Builds dimensions and facts
6. ✅ `dedupe_consolidate` - Deduplication (handled in normalizer)
7. ✅ `rank` - Ranks jobs by score
8. ✅ `dbt_tests` - Validates data quality
9. ✅ `publish_hyper` - Exports to Tableau
10. ✅ `notify_webhook_daily` - Sends summary
11. ✅ `end` - Dummy task

### 8.2 Check Final Results

```bash
# Complete summary
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT 
    'Raw Jobs' as stage, COUNT(*) as count FROM raw.job_postings_raw
UNION ALL
SELECT 
    'Staged Jobs', COUNT(*) FROM staging.job_postings_stg
UNION ALL
SELECT 
    'Companies', COUNT(*) FROM marts.dim_companies
UNION ALL
SELECT 
    'Ranked Jobs', COUNT(*) FROM marts.fact_jobs WHERE rank_score IS NOT NULL;
"
```

**Expected Output:**
```
   stage    | count 
------------+-------
 Raw Jobs   |   20+
 Staged Jobs|   20+
 Companies  |   10+
 Ranked Jobs|   20+
```

## Step 9: Troubleshooting

### Common Issues

**1. DAG not appearing:**
```bash
# Check DAG syntax
docker-compose exec airflow-webserver airflow dags list

# Check for import errors
docker-compose logs airflow-scheduler | grep -i error
```

**2. API key errors:**
- Verify `JSEARCH_API_KEY` is set in Airflow Variables
- Check task logs for API errors
- Verify API key is valid

**3. Database connection errors:**
- Check postgres container is running: `docker-compose ps postgres`
- Verify connection in Airflow UI: Admin → Connections
- Check database password in secrets file

**4. dbt tests failing:**
- Check if models have data: `SELECT COUNT(*) FROM marts.fact_jobs;`
- Verify dbt can connect: Check `dbt_models_core` task logs
- Check for null values in required fields

**5. Webhook not sending:**
- Check if `WEBHOOK_URL` is configured
- Verify webhook URL is valid
- Check task logs for errors (task won't fail DAG on webhook errors)

## Step 10: Re-run Tests

### 10.1 Test Idempotency

Run the DAG again without clearing data:
```bash
# Trigger DAG again
docker-compose exec airflow-webserver airflow dags trigger jobs_etl_daily
```

**Expected:**
- No duplicate rows (hash_key deduplication works)
- `last_seen_at` updated for existing jobs
- `first_seen_at` preserved

### 10.2 Verify Deduplication

```bash
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT 
    hash_key,
    COUNT(*) as occurrences,
    MIN(first_seen_at) as first_seen,
    MAX(last_seen_at) as last_seen
FROM staging.job_postings_stg
GROUP BY hash_key
HAVING COUNT(*) > 1;
"
```

**Expected:** Should return 0 rows (no duplicates).

## Success Criteria

✅ **All tasks complete successfully**  
✅ **Data flows through all stages** (raw → staging → marts)  
✅ **Jobs are ranked** (rank_score populated)  
✅ **dbt tests pass** (no data quality issues)  
✅ **Hyper file created** (Tableau export ready)  
✅ **Webhook notification sent** (if configured)  
✅ **No duplicate jobs** (hash_key deduplication works)  
✅ **Re-runs are idempotent** (no duplicates on re-run)

## Next Steps

Once MVP testing is successful:
1. Review Phase 0.5 Definition of Done checklist
2. Document any issues found
3. Proceed to Phase 1 - Enrichment & Data Quality features

## Quick Reference Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f airflow-scheduler

# Trigger DAG
docker-compose exec airflow-webserver airflow dags trigger jobs_etl_daily

# Check DAG status
docker-compose exec airflow-webserver airflow dags list-runs -d jobs_etl_daily

# Connect to database
docker-compose exec postgres psql -U job_etl_user -d job_etl

# Check service status
docker-compose ps
```

