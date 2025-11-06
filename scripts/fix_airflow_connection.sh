#!/bin/bash
# Fix Airflow postgres_default connection
# This script recreates the connection with the correct password

set -e

echo "=========================================="
echo "Fixing Airflow postgres_default connection"
echo "=========================================="

# Get password from secret file
if [ ! -f "secrets/database/postgres_password.txt" ]; then
    echo "Error: secrets/database/postgres_password.txt not found"
    echo "Please create it first:"
    echo "  echo 'your_password' > secrets/database/postgres_password.txt"
    exit 1
fi

PASSWORD=$(cat secrets/database/postgres_password.txt)
POSTGRES_USER=${POSTGRES_USER:-job_etl_user}
POSTGRES_DB=${POSTGRES_DB:-job_etl}

echo "Deleting old connection (if exists)..."
docker-compose exec airflow-webserver airflow connections delete postgres_default 2>/dev/null || echo "Connection didn't exist (that's okay)"

echo "Creating new connection..."
docker-compose exec airflow-webserver airflow connections add \
  'postgres_default' \
  --conn-type 'postgres' \
  --conn-host 'postgres' \
  --conn-login "$POSTGRES_USER" \
  --conn-password "$PASSWORD" \
  --conn-schema "$POSTGRES_DB" \
  --conn-port '5432'

echo ""
echo "=========================================="
echo "Connection fixed successfully!"
echo "=========================================="
echo ""
echo "Verify connection:"
echo "  docker-compose exec airflow-webserver airflow connections list"
echo ""

