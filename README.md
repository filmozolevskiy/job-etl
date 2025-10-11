# Job-ETL: Incremental, Microservice-Based ETL for Job Postings

## Quick Start (One Command)

```bash
docker compose up --build
```

This will:
- Start PostgreSQL database
- Launch Airflow web UI
- Initialize all required schemas
- Make the system ready for development

## Access Points
- **Airflow UI**: http://localhost:8080
- **PostgreSQL**: localhost:5432
- **pgAdmin** (if enabled): http://localhost:5050

## Next Steps
1. Configure your API keys in `secrets/`
2. Update `config/sources.yml` with your data sources
3. Trigger the `jobs_etl_daily` DAG in Airflow UI