# Troubleshooting Guide

## Common Issues and Solutions

### Issue: Airflow Connection `postgres_default` InvalidToken Error

**Error:**
```
cryptography.fernet.InvalidToken
The conn_id `postgres_default` isn't defined
```

**Cause:**
The Airflow connection exists but the password can't be decrypted, usually because:
- The Fernet key changed
- The connection was created with a different Fernet key
- Connection corruption

**Solution 1: Recreate the Connection (Recommended)**

Via Airflow UI:
1. Go to Admin → Connections
2. Delete `postgres_default` connection
3. Add new connection:
   - Connection Id: `postgres_default`
   - Connection Type: `Postgres`
   - Host: `postgres`
   - Schema: `job_etl`
   - Login: `job_etl_user`
   - Password: (from `secrets/database/postgres_password.txt`)
   - Port: `5432`
4. Save

Via CLI:
```bash
# Get the password
cat secrets/database/postgres_password.txt

# Delete old connection
docker-compose exec airflow-webserver airflow connections delete postgres_default

# Create new connection
docker-compose exec airflow-webserver airflow connections add \
  'postgres_default' \
  --conn-type 'postgres' \
  --conn-host 'postgres' \
  --conn-login 'job_etl_user' \
  --conn-password 'YOUR_PASSWORD_HERE' \
  --conn-schema 'job_etl' \
  --conn-port '5432'
```

**Solution 2: Re-run airflow-init**

This will recreate the connection:
```bash
# Stop services
docker-compose down

# Remove Airflow metadata database (if you want a fresh start)
docker volume rm job-etl_airflow_postgres_data

# Re-initialize
docker-compose up -d postgres airflow-postgres redis
docker-compose run --rm airflow-init

# Start services
docker-compose up -d
```

**Solution 3: Use Fallback (Current Implementation)**

The code now automatically falls back to reading from:
- Environment variables: `POSTGRES_HOST`, `POSTGRES_USER`, etc.
- Secret file: `/run/secrets/postgres_password`

This should work even if the connection is broken. The error you saw was before this fallback was implemented.

### Issue: Missing DATABASE_URL Environment Variable

**Error:**
```
DATABASE_URL must be configured via Airflow connection 'postgres_default' 
or environment variable 'DATABASE_URL'
```

**Solution:**
The code now automatically builds DATABASE_URL from individual components:
- `POSTGRES_HOST` (default: `postgres`)
- `POSTGRES_PORT` (default: `5432`)
- `POSTGRES_USER` (default: `job_etl_user`)
- `POSTGRES_DB` (default: `job_etl`)
- Password from `/run/secrets/postgres_password`

These are now set in `docker-compose.yml` for both webserver and scheduler.

**Verify:**
```bash
# Check environment variables are set
docker-compose exec airflow-scheduler env | grep POSTGRES

# Check secret is mounted
docker-compose exec airflow-scheduler cat /run/secrets/postgres_password
```

### Issue: API Key Not Found

**Error:**
```
JSEARCH_API_KEY must be set as an Airflow Variable or environment variable
```

**Solution:**
1. Get your API key from OpenWebNinja (or your provider)
2. Add it to Airflow Variables:
   - Go to Admin → Variables
   - Add: `JSEARCH_API_KEY` = `your_api_key_here`

Or set in `.env` and it will be available as environment variable.

### Issue: Email Not Sending

**Symptoms:**
- Task completes but no email received
- Logs show SMTP connection/auth errors

**Solution:**
1. Configure SMTP settings for Airflow containers:
   - `SMTP_HOST` (required)
   - `SMTP_FROM` (required)
   - `NOTIFY_TO` (required)
   - `SMTP_USER` (optional) and `secrets/notifications/smtp_password.txt` if auth required

**Note:** Notification failures don't fail the DAG - they're logged but the pipeline continues.

### Issue: dbt Tests Failing

**Error:**
```
DBT TESTS TASK - Some tests failed
```

**Common Causes:**
1. **No data in tables:** Tests expect data but tables are empty
   - Solution: Run extract → normalize → rank tasks first
2. **Null values in required fields:** Tests expect `not_null` but data has nulls
   - Solution: Check data quality, fix normalization
3. **Duplicate hash_keys:** Tests expect `unique` but duplicates exist
   - Solution: Check deduplication logic

**Debug:**
```bash
# Check if data exists
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT COUNT(*) FROM marts.fact_jobs;
"

# Check for nulls
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT COUNT(*) FROM marts.fact_jobs WHERE hash_key IS NULL;
"

# Check for duplicates
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "
SELECT hash_key, COUNT(*) as count 
FROM marts.fact_jobs 
GROUP BY hash_key 
HAVING COUNT(*) > 1;
"
```

### Issue: Services Can't Import Python Modules

**Error:**
```
ModuleNotFoundError: No module named 'services'
```

**Solution:**
The code automatically adds `/opt/airflow` to `sys.path`. If this fails:
1. Check that services directory is mounted:
   ```bash
   docker-compose exec airflow-scheduler ls -la /opt/airflow/services/
   ```
2. Verify Python path in logs
3. Check file permissions

### Issue: Docker Compose Services Not Starting

**Error:**
```
Error starting service: ...
```

**Solutions:**
1. **Check ports are available:**
   ```bash
   # Check if ports are in use
   netstat -an | grep 5432
   netstat -an | grep 8080
   ```

2. **Check Docker is running:**
   ```bash
   docker ps
   ```

3. **Check secrets exist:**
   ```bash
   ls -la secrets/database/postgres_password.txt
   ls -la secrets/airflow/airflow_postgres_password.txt
   ```

4. **Rebuild containers:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Issue: Database Connection Timeout

**Error:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**
1. **Check postgres is running:**
   ```bash
   docker-compose ps postgres
   docker-compose logs postgres
   ```

2. **Check network:**
   ```bash
   docker-compose exec airflow-scheduler ping postgres
   ```

3. **Check credentials:**
   ```bash
   # Test connection manually
   docker-compose exec postgres psql -U job_etl_user -d job_etl -c "SELECT 1;"
   ```

## Quick Diagnostic Commands

```bash
# Check all services status
docker-compose ps

# Check service logs
docker-compose logs -f airflow-scheduler
docker-compose logs -f postgres

# Check Airflow connections
docker-compose exec airflow-webserver airflow connections list

# Check Airflow variables
docker-compose exec airflow-webserver airflow variables list

# Check database connectivity
docker-compose exec postgres psql -U job_etl_user -d job_etl -c "SELECT version();"

# Check DAG status
docker-compose exec airflow-webserver airflow dags list
docker-compose exec airflow-webserver airflow dags list-runs -d jobs_etl_daily

# Check environment variables
docker-compose exec airflow-scheduler env | grep -E "POSTGRES|DATABASE"
```

## Getting Help

If issues persist:
1. Check logs: `docker-compose logs <service-name>`
2. Review error messages in Airflow UI
3. Verify configuration matches this guide
4. Check GitHub issues for similar problems

