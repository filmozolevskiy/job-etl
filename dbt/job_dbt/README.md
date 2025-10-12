# Job ETL dbt Project

This dbt project transforms raw job posting data into clean, normalized datasets for Tableau visualization.

## Project Structure

```
dbt/job_dbt/
├── models/
│   ├── raw/          # Raw data sources and initial views
│   ├── staging/      # Cleaned and normalized tables
│   ├── int/          # Intermediate enrichment models
│   └── marts/        # Final dimensions and facts for Tableau
├── seeds/            # CSV files for reference data (enums, mappings)
├── macros/           # Reusable SQL functions
├── tests/            # Custom data tests
├── dbt_project.yml   # Project configuration
└── profiles.yml.example  # Database connection template

## Setup

### Local Development

1. Copy the profiles example to your dbt config directory:
   ```bash
   cp profiles.yml.example ~/.dbt/profiles.yml
   ```

2. Update the credentials in `~/.dbt/profiles.yml` to match your local PostgreSQL setup.

3. Test the connection:
   ```bash
   dbt debug --project-dir dbt/job_dbt
   ```

### Docker Compose

When running in Docker Compose, dbt is available in the Airflow containers with the `docker` profile configured.

## Usage

### Running dbt

**Important Note:** When running dbt in the Docker containers, you must specify writable paths for `--target-path` and `--log-path` since the dbt directory is mounted as read-only.

```bash
# From within the Airflow container (docker exec job-etl-airflow-scheduler bash):
DBT_CMD="/home/airflow/.local/bin/dbt"
PROJECT_DIR="/opt/airflow/dbt/job_dbt"
PROFILES_DIR="/tmp/dbt_test"  # Or create a profiles.yml first
TARGET_PATH="/tmp/dbt_target"
LOG_PATH="/tmp/dbt_logs"

# Compile models (check for syntax errors)
$DBT_CMD compile --project-dir $PROJECT_DIR --profiles-dir $PROFILES_DIR --target-path $TARGET_PATH --log-path $LOG_PATH

# Run all models
$DBT_CMD run --project-dir $PROJECT_DIR --profiles-dir $PROFILES_DIR --target-path $TARGET_PATH --log-path $LOG_PATH

# Run tests
$DBT_CMD test --project-dir $PROJECT_DIR --profiles-dir $PROFILES_DIR --target-path $TARGET_PATH --log-path $LOG_PATH

# Load seed data
$DBT_CMD seed --project-dir $PROJECT_DIR --profiles-dir $PROFILES_DIR --target-path $TARGET_PATH --log-path $LOG_PATH

# Parse project (check for syntax errors)
$DBT_CMD parse --project-dir $PROJECT_DIR --profiles-dir $PROFILES_DIR --target-path $TARGET_PATH --log-path $LOG_PATH

# Generate documentation
$DBT_CMD docs generate --project-dir $PROJECT_DIR --profiles-dir $PROFILES_DIR --target-path $TARGET_PATH --log-path $LOG_PATH
```

**For local development** (with profiles.yml in ~/.dbt/):

```bash
cd dbt/job_dbt
dbt compile
dbt run
dbt test
```

## Data Model

### Schemas

- **raw**: Provider JSON + minimal parsed fields
- **staging**: Flattened provider-agnostic tables
- **marts**: Curated dimensions and facts (for Tableau)

### Key Tables

- `raw.job_postings_raw` - Raw JSON payloads from APIs
- `staging.job_postings_stg` - Normalized job postings
- `marts.dim_companies` - Company dimension
- `marts.fact_jobs` - Job facts with rankings

## Testing Strategy

- **Unique & Not Null**: Primary keys and required fields
- **Accepted Values**: Enum columns (remote_type, contract_type, etc.)
- **Referential Integrity**: Foreign key relationships
- **Data Quality**: Custom tests for business rules

## Development Workflow

1. Create models in the appropriate directory (staging, int, or marts)
2. Add tests in schema.yml files
3. Run `dbt compile` to check syntax
4. Run `dbt run` to materialize models
5. Run `dbt test` to validate data quality
6. Document changes in model .yml files

