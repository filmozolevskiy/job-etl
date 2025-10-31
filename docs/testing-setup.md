# Testing Setup Guide

## Current Status: Integration Tests Disabled ⚠️

**Integration tests are currently DISABLED for safety.** All tests in `tests/integration/` are skipped and serve as placeholders.

To run the project tests:
```bash
pytest tests/unit/ -v  # Unit tests only (SAFE - no database required)
```

## Why Integration Tests Are Disabled

The Job-ETL project includes integration tests that verify end-to-end functionality with a real PostgreSQL database. **These tests modify and delete database records**, which poses a risk if run against development or production databases.

Until a dedicated test database is configured, integration tests remain disabled.

## How to Re-Enable Integration Tests

When you're ready to enable integration tests:

1. **Set up dedicated test database** (see instructions below)
2. **Restore test implementations** from git history:
   ```bash
   git log --oneline tests/integration/
   git show <commit-hash>:tests/integration/test_normalizer_integration.py
   ```
3. **Remove skip decorators** from test files
4. **Configure DATABASE_URL** to point to test database
5. **Run tests**: `pytest tests/integration/ -v`

## ⚠️ Critical Warning

Integration tests will **DELETE data** from database tables:

### Normalizer Integration Tests
- **Deletes ALL rows** from:
  - `raw.job_postings_raw`
  - `staging.job_postings_stg`

### JSearch Integration Tests  
- **Deletes matching rows** from `raw.job_postings_raw` where:
  - `source = 'jsearch'` OR
  - `source LIKE 'test%'` OR
  - `provider_job_id LIKE 'test_%'`

## Recommended Setup: Separate Test Database

### Step 1: Create Test Database

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create test database
CREATE DATABASE job_etl_test;

-- Create user if needed
CREATE USER job_etl_user WITH PASSWORD 'job_etl_pass';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE job_etl_test TO job_etl_user;
```

### Step 2: Set Up Schemas and Tables

Run the same schema setup as your main database:

```bash
# Apply migrations/schema to test database
psql -U job_etl_user -d job_etl_test -f db/schema.sql
```

Or if using dbt:

```bash
# Update profiles.yml to include test target
# Then run:
dbt run --target test
```

### Step 3: Configure Environment

Set `DATABASE_URL` to point to your test database before running integration tests:

#### Linux/Mac:
```bash
export DATABASE_URL="postgresql://job_etl_user:job_etl_pass@localhost:5432/job_etl_test"
pytest tests/integration/ -v
```

#### Windows PowerShell:
```powershell
$env:DATABASE_URL="postgresql://job_etl_user:job_etl_pass@localhost:5432/job_etl_test"
pytest tests/integration/ -v
```

#### Windows Command Prompt:
```cmd
set DATABASE_URL=postgresql://job_etl_user:job_etl_pass@localhost:5432/job_etl_test
pytest tests/integration/ -v
```

### Step 4: Add to .env (Optional)

You can create a separate `.env.test` file:

```bash
# .env.test
DATABASE_URL=postgresql://job_etl_user:job_etl_pass@localhost:5432/job_etl_test
```

Then load it before tests:

```bash
set -a
source .env.test
set +a
pytest tests/integration/ -v
```

## Running Tests Safely

### Run Unit Tests (No Database Required) ✅ RECOMMENDED
```bash
pytest tests/unit/ -v
```

### Run All Tests (Includes Skipped Integration Tests)
```bash
pytest -v
# Integration tests will be skipped automatically
```

### Run Integration Tests (Currently Disabled)
```bash
# These will be skipped until you:
# 1. Set up dedicated test database
# 2. Restore test implementations from git history
# 3. Remove @pytest.mark.skip decorators
pytest tests/integration/ -v
```

### Run Specific Test File
```bash
pytest tests/integration/test_normalizer_integration.py -v
```

### Skip Integration Tests
```bash
pytest -m "not integration" -v
```

## Docker Compose Test Database (Alternative)

You can also spin up a temporary test database with Docker:

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  postgres_test:
    image: postgres:15
    environment:
      POSTGRES_DB: job_etl_test
      POSTGRES_USER: job_etl_user
      POSTGRES_PASSWORD: job_etl_pass
    ports:
      - "5433:5432"  # Different port to avoid conflicts
    volumes:
      - ./db/schema.sql:/docker-entrypoint-initdb.d/schema.sql
```

Start it:
```bash
docker-compose -f docker-compose.test.yml up -d
```

Use it:
```bash
export DATABASE_URL="postgresql://job_etl_user:job_etl_pass@localhost:5433/job_etl_test"
pytest tests/integration/ -v
```

Clean up:
```bash
docker-compose -f docker-compose.test.yml down -v
```

## Test Data Cleanup

Integration tests automatically clean up test data:
- **Before each test**: Clears relevant tables
- **After each test**: Clears relevant tables again

This ensures test isolation but means **any data in those tables will be deleted**.

## Best Practices

1. ✅ **Always use a separate test database** for integration tests
2. ✅ **Never run integration tests** against production databases
3. ✅ **Set DATABASE_URL explicitly** before running integration tests  
4. ✅ **Use unit tests** when possible (faster, safer)
5. ✅ **Keep test data minimal** to speed up tests
6. ⚠️ **Backup your data** before running integration tests on shared databases

## Quick Reference

| Test Type | Command | Database Access | Data Safety |
|-----------|---------|----------------|-------------|
| Unit Tests | `pytest tests/unit/` | No database | ✅ Safe |
| Integration Tests | `pytest tests/integration/` | Yes, modifies data | ⚠️ Use test DB |
| All Tests | `pytest` | Yes for integration | ⚠️ Use test DB |

## Troubleshooting

### "Tests are failing with connection errors"
- Ensure PostgreSQL is running
- Verify DATABASE_URL is set correctly
- Check user has proper permissions

### "Tests are passing but data is missing from dev database"
- You likely ran integration tests against your dev database
- Restore from backup or re-populate data
- Set up separate test database for future runs

### "How do I know which database tests are using?"
Add this at the start of a test:
```python
print(f"Using database: {database_url}")
```

Or check the pytest output for connection information.

