# Job-ETL: Incremental, Microservice-Based ETL for Job Postings

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

4. **Start the database:**
   ```bash
   docker-compose up -d postgres
   ```

5. **Verify setup:**
   ```bash
   # Check if database is running
   docker-compose ps
   
   # Connect to database and verify schemas
   docker-compose exec postgres psql -U job_etl_user -d job_etl -c "\dn"
   ```

## Current Status

✅ **Phase 0 - Step 3 Complete**: PostgreSQL database bootstrap
- Database schemas created: `raw`, `staging`, `marts`
- Core tables with proper indexes and constraints
- Deduplication function (`generate_hash_key`)
- Named volumes for data persistence
- Docker secrets for password management

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
- **Airflow Webserver**: 8080
- **pgAdmin**: 8081 (optional, use `--profile tools`)
- **Redis**: 6379

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

### Database Management
```bash
# Start database
docker-compose up -d postgres

# Connect to database
docker-compose exec postgres psql -U job_etl_user -d job_etl

# Stop database
docker-compose down
```

### View Logs
```bash
docker-compose logs postgres
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