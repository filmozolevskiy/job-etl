#!/bin/bash
# Bash script to connect to PostgreSQL database
# Usage: ./scripts/query_postgres.sh [query]
# Example: ./scripts/query_postgres.sh "SELECT COUNT(*) FROM raw.job_postings_raw;"

CONTAINER_NAME="job-etl-postgres"
DB_USER="job_etl_user"
DB_NAME="job_etl"
PASSWORD_FILE="./secrets/database/postgres_password.txt"

# Read password from secrets file
if [ -f "$PASSWORD_FILE" ]; then
    PASSWORD=$(cat "$PASSWORD_FILE" | tr -d '\r\n')
else
    echo "Error: Password file not found at $PASSWORD_FILE"
    exit 1
fi

# Set PGPASSWORD environment variable for psql
export PGPASSWORD="$PASSWORD"

if [ -z "$1" ]; then
    # Interactive mode
    echo "Connecting to PostgreSQL..."
    echo "Database: $DB_NAME | User: $DB_USER"
    echo "Type \q to exit"
    echo ""
    docker exec -it "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"
else
    # Execute query
    echo "Executing query..."
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "$1"
fi



