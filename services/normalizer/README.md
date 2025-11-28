# Normalizer Service

The normalizer service transforms raw job posting JSON from various providers into a canonical format that matches our standardized staging schema.

## Purpose

The normalizer sits between raw data ingestion and downstream processing:

```
[Source Extractor] → raw.job_postings_raw
         ↓
   [NORMALIZER] ← You are here
         ↓
staging.job_postings_stg → [Enricher] → [Ranker] → [Publisher]
```

## Key Features

### 1. Provider-Agnostic Transformation
- Converts provider-specific JSON (JSearch, LinkedIn, Indeed, etc.) into our standard schema
- Maps varying field names and formats to consistent structure
- Handles missing data gracefully with sensible defaults

### 2. Deduplication via Hash Key
- Generates unique `hash_key` from `md5(company|title|location)`
- Normalizes whitespace and case before hashing
- Enables detection of duplicate postings across sources

### 3. Idempotent Upserts
- Uses PostgreSQL `ON CONFLICT` to handle duplicates
- New jobs: Insert with `first_seen_at` timestamp
- Existing jobs: Update `last_seen_at` timestamp
- Safe to run multiple times without creating duplicates

### 4. Data Quality
- Validates required fields (company, title, location)
- Enforces enum constraints (remote_type, contract_type, company_size)
- Applies defaults for missing optional fields
- Logs warnings for invalid data

## Architecture

```
normalizer/
├── __init__.py           # Package initialization
├── hash_generator.py     # Hash key generation (pure functions)
├── normalize.py          # Core transformation logic
├── db_operations.py      # Database read/write operations
├── main.py              # CLI entry point
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Component Responsibilities

**hash_generator.py**
- Pure functions for hash key generation
- Whitespace normalization
- Hash validation

**normalize.py**
- Field mapping and transformation
- Type conversion and validation
- Default value application
- Enum normalization

**db_operations.py**
- Database connection management
- Fetch raw jobs from `raw.job_postings_raw`
- Upsert normalized jobs to `staging.job_postings_stg`
- Statistics and monitoring queries

**main.py**
- Command-line interface
- Orchestrates fetch → normalize → upsert flow
- Logging and error handling
- Exit codes for Airflow integration

## Usage

### From Command Line

```bash
# Process all raw jobs
python -m services.normalizer.main

# Process only JSearch jobs
python -m services.normalizer.main --source jsearch

# Process up to 100 jobs
python -m services.normalizer.main --limit 100

# Process recent jobs only
python -m services.normalizer.main --min-collected-at "2025-10-26T00:00:00"

# Dry run (no database writes)
python -m services.normalizer.main --dry-run

# Verbose logging
python -m services.normalizer.main --verbose
```

### From Airflow

```python
from airflow.operators.python import PythonOperator

def run_normalizer():
    """Call normalizer as a Python function"""
    from services.normalizer.main import run_normalizer
    from services.normalizer.db_operations import NormalizerDB
    
    db = NormalizerDB(os.getenv('DATABASE_URL'))
    stats = run_normalizer(db, source='jsearch')
    
    print(f"Normalized {stats['normalized']} jobs")

normalize_task = PythonOperator(
    task_id='normalize',
    python_callable=run_normalizer,
    dag=dag
)
```

### From Docker

```bash
docker run --rm \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  job-etl-normalizer:latest \
  python -m services.normalizer.main --source jsearch
```

## Data Flow

### Input: `raw.job_postings_raw`

```sql
raw_id       | uuid
source       | text (e.g., 'jsearch')
payload      | jsonb (provider-specific structure)
collected_at | timestamptz
```

### Output: `staging.job_postings_stg`

```sql
hash_key                     | text (PRIMARY KEY)
provider_job_id              | text
job_link                     | text
job_title                    | text (REQUIRED)
company                      | text (REQUIRED)
company_size                 | text (enum, default: 'unknown')
location                     | text (REQUIRED)
remote_type                  | text (enum: remote/hybrid/onsite/unknown)
contract_type                | text (enum: full_time/part_time/contract/intern/temp/unknown)
seniority_level              | text (enum: junior/intermediate/senior/unknown, filled by enricher)
seniority_enrichment_status  | text (enum: not_tried/upgraded/failed_to_upgrade, default 'not_tried')
salary_min                   | numeric
salary_max                   | numeric
salary_currency              | text
description                  | text
skills_raw                   | text[]
posted_at                    | timestamptz
apply_url                    | text
source                       | text (REQUIRED)
first_seen_at                | timestamptz (auto)
last_seen_at                 | timestamptz (auto)
```

## Hash Key Generation

The hash key ensures we don't store duplicate jobs. Two jobs are considered duplicates if they have the same:
- Company name
- Job title
- Location

After normalizing whitespace and case:

```python
# These create the same hash:
generate_hash_key("ACME Corp", "Data Engineer", "Montreal, QC")
generate_hash_key("acme  corp", "data  engineer", "montreal, qc")

# Result: "a1b2c3d4e5f6789012345678901234ab"
```

## Error Handling

### Exit Codes

- `0`: Success
- `1`: Partial failure (some jobs failed normalization)
- `2`: Fatal error (database connection, etc.)
- `130`: Interrupted by user (Ctrl+C)

### Logging Levels

- **INFO**: Normal operation (jobs processed, stats)
- **WARNING**: Recoverable issues (invalid field values, missing optional data)
- **ERROR**: Failures (normalization errors, database errors)
- **DEBUG**: Detailed execution (enabled with `--verbose`)

### Common Errors

**Missing Required Fields**
```
NormalizationError: job_title is required and must be a non-empty string
```
Solution: Ensure source adapter provides all required fields

**Database Connection Failed**
```
DatabaseError: Failed to connect to database: connection refused
```
Solution: Check `DATABASE_URL` environment variable and database availability

**Invalid Enum Values**
```
WARNING: Invalid remote_type value, using default
```
Solution: Map provider values to our enums in source adapter

## Testing

See `tests/unit/test_normalizer.py` and `tests/integration/test_normalizer_integration.py`

```bash
# Run unit tests
pytest tests/unit/test_normalizer.py -v

# Run integration tests (requires database)
pytest tests/integration/test_normalizer_integration.py -v

# Run with coverage
pytest tests/ --cov=services.normalizer --cov-report=html
```

## Configuration

### Environment Variables

```bash
# Required
DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# Optional (with defaults)
LOG_LEVEL="INFO"  # or DEBUG, WARNING, ERROR
```

### Database Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]
```

Examples:
- Local: `postgresql://job_etl_user:job_etl_pass@localhost:5432/job_etl`
- Docker: `postgresql://job_etl_user:job_etl_pass@postgres:5432/job_etl`
- AWS RDS: `postgresql://admin:secret@mydb.region.rds.amazonaws.com:5432/job_etl`

## Monitoring

### Statistics Query

```sql
SELECT 
    source,
    COUNT(*) as total_jobs,
    COUNT(DISTINCT hash_key) as unique_jobs,
    MIN(first_seen_at) as earliest_job,
    MAX(last_seen_at) as latest_seen
FROM staging.job_postings_stg
GROUP BY source;
```

### Check Recent Normalizations

```sql
SELECT 
    COUNT(*) as jobs_normalized_last_hour
FROM staging.job_postings_stg
WHERE last_seen_at >= NOW() - INTERVAL '1 hour';
```

## Troubleshooting

### No jobs found to process

**Symptom**: `WARNING: No raw jobs found to process`

**Causes**:
1. Source extractor hasn't run yet
2. All jobs already normalized
3. Source filter doesn't match any jobs

**Solutions**:
- Run source extractor first
- Check `--source` filter value
- Verify raw table contents: `SELECT COUNT(*) FROM raw.job_postings_raw;`

### Jobs failing normalization

**Symptom**: `WARNING: Failed to normalize job posting`

**Causes**:
1. Missing required fields in source adapter
2. Invalid data types
3. Constraint violations

**Solutions**:
- Check source adapter's `map_to_common()` implementation
- Verify raw payload structure
- Review normalizer logs for specific errors

### Database connection issues

**Symptom**: `DatabaseError: Failed to connect to database`

**Causes**:
1. Wrong DATABASE_URL
2. Database not running
3. Network issues
4. Insufficient permissions

**Solutions**:
- Verify DATABASE_URL format
- Check database is running: `docker ps | grep postgres`
- Test connection: `psql $DATABASE_URL`
- Verify user permissions

## Performance Considerations

### Batch Size

The normalizer processes all fetched jobs in a single transaction. For large volumes:

```bash
# Process in chunks
python -m services.normalizer.main --limit 1000
```

### Indexing

The staging table has indexes on:
- `hash_key` (PRIMARY KEY)
- `source`
- `company`
- `posted_at`

These speed up lookups and upserts.

### Connection Pooling

Currently uses single connections per run. For high-throughput scenarios, consider:
- Connection pooling (pgbouncer)
- Async operations (asyncpg)
- Parallel processing (multiprocessing)

## Future Enhancements

- [ ] Async/parallel processing for high volumes
- [ ] Configurable field mappings (YAML)
- [ ] Custom validation rules per source
- [ ] Metrics export (Prometheus)
- [ ] Data quality reports
- [ ] Automatic schema evolution

## Related Documentation

- [Project Specification](../../docs/specification.md)
- [Data Model Guidelines](../../docs/specification.md#5-data-model-postgres--dbt)
- [Source Extractor README](../source_extractor/README.md)
- [Airflow DAG Documentation](../../airflow/dags/README.md)

