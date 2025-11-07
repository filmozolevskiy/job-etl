# Fixing Airflow Container Issues

## Issues Fixed

1. **Command not found errors**: Changed from `exec webserver`/`exec scheduler` to `airflow webserver`/`airflow scheduler`
2. **FERNET_KEY mismatch**: Fixed connection deletion to use SQL directly instead of Airflow CLI
3. **Missing environment variables**: Added proper environment variable setup in command scripts

## Steps to Fix

### 1. Generate Required Keys (if not already done)

```bash
python scripts/generate_airflow_keys.py
```

Add the output to your `.env` file:
```
AIRFLOW__CORE__FERNET_KEY=<generated_key>
AIRFLOW__WEBSERVER__SECRET_KEY=<generated_key>
AIRFLOW_ADMIN_PASSWORD=<your_password>
```

### 2. Ensure Environment Variables are Set

Create or update `.env` file in the project root with:
```env
# Database
POSTGRES_USER=job_etl_user
POSTGRES_DB=job_etl
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Airflow
AIRFLOW__CORE__FERNET_KEY=<from generate_airflow_keys.py>
AIRFLOW__WEBSERVER__SECRET_KEY=<from generate_airflow_keys.py>
AIRFLOW_ADMIN_PASSWORD=<your_password>
AIRFLOW_POSTGRES_PASSWORD=<from secrets/airflow/airflow_postgres_password.txt>

# Timezone
TIMEZONE=America/Toronto

# Optional: SMTP settings
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_FROM=
NOTIFY_TO=
```

### 3. Rebuild and Start Containers

```bash
# Stop all containers
docker-compose down

# Optionally remove Airflow database volume if you want a fresh start
# WARNING: This will delete all Airflow metadata
docker volume rm job-etl_airflow_postgres_data

# Rebuild images (if needed)
docker-compose build --no-cache airflow-webserver airflow-scheduler airflow-init

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f airflow-init
docker-compose logs -f airflow-webserver
docker-compose logs -f airflow-scheduler
```

### 4. Verify Containers are Running

```bash
docker-compose ps
```

All containers should show "Up" status.

### 5. Access Airflow UI

Open http://localhost:8080 in your browser and login with:
- Username: `admin`
- Password: (value of `AIRFLOW_ADMIN_PASSWORD` from `.env`)

## Troubleshooting

### If containers still restart:

1. Check logs: `docker-compose logs airflow-webserver airflow-scheduler`
2. Verify FERNET_KEY is set: `docker-compose exec airflow-webserver env | grep FERNET_KEY`
3. Check database connection: `docker-compose exec airflow-postgres pg_isready -U airflow`

### If FERNET_KEY errors persist:

1. Stop containers: `docker-compose down`
2. Remove Airflow database volume: `docker volume rm job-etl_airflow_postgres_data`
3. Start fresh: `docker-compose up -d`

### If connection errors occur:

The airflow-init script now deletes connections directly via SQL to avoid FERNET_KEY mismatch issues. If problems persist, you can manually delete connections:

```bash
docker-compose exec airflow-postgres psql -U airflow -d airflow -c "DELETE FROM connection WHERE conn_id = 'postgres_default';"
```

Then restart the init container:
```bash
docker-compose up airflow-init
```
