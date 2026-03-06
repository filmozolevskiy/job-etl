#!/usr/bin/env bash
# Prepare environment for running the DAG.
# Run from project root: ./scripts/prepare_env.sh

set -e
cd "$(dirname "$0")/.."

echo "=== Job-ETL Environment Preparation ==="

# Check .env exists
if [[ ! -f .env ]]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
  echo "  -> Edit .env and set required values (AIRFLOW__CORE__FERNET_KEY, etc.)"
fi

# Ensure AIRFLOW_POSTGRES_PASSWORD in .env matches the secret file (required for airflow-init)
SECRET_FILE="secrets/airflow/airflow_postgres_password.txt"
if [[ -f "$SECRET_FILE" && -f .env ]]; then
  AIRFLOW_PG_PASS=$(tr -d '\n\r' < "$SECRET_FILE")
  if grep -q "^AIRFLOW_POSTGRES_PASSWORD=" .env 2>/dev/null; then
    # Update existing line to match secret
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^AIRFLOW_POSTGRES_PASSWORD=.*|AIRFLOW_POSTGRES_PASSWORD=$AIRFLOW_PG_PASS|" .env
    else
      sed -i "s|^AIRFLOW_POSTGRES_PASSWORD=.*|AIRFLOW_POSTGRES_PASSWORD=$AIRFLOW_PG_PASS|" .env
    fi
    echo "  -> Synced AIRFLOW_POSTGRES_PASSWORD in .env with secret file"
  else
    echo "AIRFLOW_POSTGRES_PASSWORD=$AIRFLOW_PG_PASS" >> .env
    echo "  -> Added AIRFLOW_POSTGRES_PASSWORD to .env"
  fi
fi

# Ensure artifacts dir exists
mkdir -p artifacts
echo "  -> artifacts/ ready"

# Check required secrets
for f in secrets/database/postgres_password.txt secrets/airflow/airflow_postgres_password.txt secrets/notifications/smtp_password.txt; do
  if [[ ! -f "$f" ]]; then
    echo "WARNING: $f missing. Create it for full functionality."
  fi
done

echo ""
echo "Next steps:"
echo "  1. docker compose up -d postgres airflow-postgres redis"
echo "  2. sleep 20"
echo "  3. docker compose run --rm airflow-init"
echo "  4. docker compose up -d"
echo "  5. Open http://localhost:8080 and add JSEARCH_API_KEY in Admin -> Variables"
echo ""
