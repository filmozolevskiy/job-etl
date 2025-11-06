# Job-ETL: Incremental, Microservice-Based ETL for Job Postings

[![CI Pipeline](https://github.com/filmozolevskiy/job-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/filmozolevskiy/job-etl/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-check%20artifacts-blue)](https://github.com/filmozolevskiy/job-etl/actions)

A learning project that builds a hands-on ETL system for ingesting, processing, and ranking job postings from 3rd-party APIs, orchestrated by Apache Airflow.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd job-etl
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

3. **Create secret files:**
   ```bash
   # Generate secure database password
   openssl rand -base64 32 > secrets/database/postgres_password.txt
   
   # Generate Airflow PostgreSQL password
   openssl rand -base64 32 > secrets/airflow/airflow_postgres_password.txt
   
   # Set restrictive permissions (Unix/Linux/Mac)
   chmod 600 secrets/database/postgres_password.txt
   chmod 600 secrets/airflow/airflow_postgres_password.txt
   ```

4. **Initialize Airflow:**
   ```bash
   # Start database services first
   docker-compose up -d postgres airflow-postgres redis
   
   # Initialize Airflow (creates admin user and connections)
   docker-compose run --rm airflow-init
   ```

5. **Start all services:**
   ```bash
   docker-compose up -d
   ```

6. **Access Airflow UI:**
   - Open browser to: http://localhost:8080
   - Username: `admin`
   - Password: Value from `.env` file (`AIRFLOW_ADMIN_PASSWORD`, default: `admin`)

7. **Verify setup:**
   ```bash
   # Check all services are running
   docker-compose ps
   
   # Check Airflow health
   curl http://localhost:8080/health
   
   # List DAGs
   docker-compose exec airflow-webserver airflow dags list
   ```

## Current Status

✅ **Phase 0 - Step 4 Complete**: Airflow (LocalExecutor) running
- PostgreSQL database with schemas: `raw`, `staging`, `marts`
- Airflow webserver and scheduler operational
- Database connections configured
- Docker Compose orchestration ready
- **GitHub Actions CI/CD** pipeline ✨

## Project Structure

```
job-etl/
├── docker-compose.yml          # Multi-service orchestration
├── .env.example               # Environment template
├── scripts/
│   └── bootstrap_db.sql       # Database initialization
├── secrets/                   # Docker secrets (not in git)
│   ├── database/
│   └── airflow/
├── airflow/                   # Airflow configuration
│   ├── Dockerfile
│   ├── requirements.txt
│   └── dags/
├── dbt/                      # dbt project
├── services/                 # Microservices
├── config/                   # Configuration files
└── tests/                    # Test suites
```

## Database Schema

### Schemas
- **`raw`**: Raw JSON data from APIs
- **`staging`**: Normalized, provider-agnostic data
- **`marts`**: Curated dimensions and facts for analytics

### Key Tables
- `raw.job_postings_raw`: Raw API responses
- `staging.job_postings_stg`: Normalized job postings
- `marts.dim_companies`: Company dimension
- `marts.fact_jobs`: Job postings with rankings

### Deduplication
Jobs are uniquely identified by: `hash_key = md5(company|title|location)`

## Important Notes

### Port Mappings
- **PostgreSQL**: 5432 (main database)
- **Airflow Webserver**: 8080 (http://localhost:8080)
- **Airflow Postgres**: 5432 (internal only)
- **pgAdmin**: 8081 (optional, use `--profile tools`)
- **Redis**: 6379 (internal only)

### Default Credentials
- **Airflow UI**: admin / admin (change `AIRFLOW_ADMIN_PASSWORD` in `.env`)
- **PostgreSQL**: job_etl_user / (from `secrets/database/postgres_password.txt`)
- **pgAdmin**: admin@example.com / admin (change in `.env`)

### Generating Keys
For production use, generate secure keys for Airflow:
```bash
# Generate Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate secret key
openssl rand -base64 32
```

Add these to your `.env` file as `AIRFLOW__CORE__FERNET_KEY` and `AIRFLOW__WEBSERVER__SECRET_KEY`.

## Next Steps

The next phase will involve:
1. Setting up Airflow with LocalExecutor
2. Creating dbt project skeleton
3. Implementing the first data source adapter
4. Building the ETL pipeline

## Development

### Continuous Integration

This project uses GitHub Actions for automated testing and quality checks:
- **Linting** with Ruff (PEP 8 compliance)
- **Testing** with pytest (unit + integration tests)
- **dbt validation** (SQL model compilation)

View CI status: https://github.com/filmozolevskiy/job-etl/actions

When CI fails, detailed error reports are automatically posted to:
- PR comments (for pull requests)
- Commit comments (for all pushes)
- GitHub issues (for main branch failures)

### Airflow Management
```bash
# Start all services
docker-compose up -d

# Access Airflow UI
open http://localhost:8080  # or visit in browser

# View logs
docker-compose logs airflow-webserver
docker-compose logs airflow-scheduler

# Trigger main DAG (after configuration)
# docker-compose exec airflow-webserver airflow dags unpause jobs_etl_daily
# docker-compose exec airflow-webserver airflow dags trigger jobs_etl_daily

# Stop all services
docker-compose down
```

### Database Management
```bash
# Connect to job_etl database
docker-compose exec postgres psql -U job_etl_user -d job_etl

# Connect to Airflow metadata database
docker-compose exec airflow-postgres psql -U airflow -d airflow

# View database schemas
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "\dn"
```

## Security

- Passwords stored in Docker secrets (not in git)
- Database user has minimal required permissions
- Secrets directory excluded from version control

## Contributing

1. Follow the phased development approach in `docs/TODO.md`
2. Ensure all acceptance criteria are met
3. Run tests before submitting changes
4. Update documentation as needed

## License

This is a learning project for educational purposes.