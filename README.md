# Job Postings ETL Pipeline

[![CI Pipeline](https://github.com/filmozolevskiy/job-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/filmozolevskiy/job-etl/actions/workflows/ci.yml)

A modular ETL pipeline that ingests job postings from different third‑party APIs, normalizes and enriches them with skills extraction, ranks them and loads them to the final tables.

**Key Features**

- **Modular ELT** – microservices for extract, normalize, enrich, rank, publish
- **Skills extraction** – spaCy + YAML keyword rules
- **Configurable ranking** – YAML weights, explainable scores
- **dbt modeling** – raw data at bronze layer; transformations in silver; business logic in gold
- **Airflow** – orchestration with Apache Airflow
- **Docker** – each ETL component in its own image

---

## Quick Start

1. Clone and enter the project:
   ```bash
   git clone <repository-url>
   cd job-etl
   ```

2. Copy env and create secrets:
   ```bash
   cp .env.example .env
   openssl rand -base64 32 > secrets/database/postgres_password.txt
   openssl rand -base64 32 > secrets/airflow/airflow_postgres_password.txt
   chmod 600 secrets/database/postgres_password.txt secrets/airflow/airflow_postgres_password.txt
   ```

3. Start services:
   ```bash
   docker-compose up -d postgres airflow-postgres redis
   docker-compose run --rm airflow-init
   docker-compose up -d
   ```

4. Open Airflow UI at http://localhost:8080

---

## Default Credentials

| Service       | Username        | Password                                      |
|---------------|-----------------|-----------------------------------------------|
| Airflow UI    | `admin`         | `admin` (set `AIRFLOW_ADMIN_PASSWORD` in `.env`) |
| PostgreSQL    | `job_etl_user`  | From `secrets/database/postgres_password.txt` |
| pgAdmin       | `admin@example.com` | `admin` (optional, `--profile tools`)      |

---

## Documentation

- [Specification](docs/specification.md)
- [ETL Flow Diagram](docs/architecture/job-etl-flow.drawio)
- [TODO](docs/TODO.md)
