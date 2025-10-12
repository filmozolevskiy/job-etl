#!/bin/bash
# Test script to verify dbt project setup
# This script should be run from within the Airflow container
# Usage: docker exec job-etl-airflow-scheduler bash /opt/airflow/dbt/job_dbt/test_dbt_setup.sh

set -e

echo "=== Testing dbt Project Setup ==="
echo ""

# Set up environment
export DBT_CMD="/home/airflow/.local/bin/dbt"
export DBT_PROJECT_DIR="/opt/airflow/dbt/job_dbt"
export DBT_PROFILES_DIR="/tmp/dbt_test"
export DBT_TARGET_PATH="/tmp/dbt_target"
export DBT_LOG_PATH="/tmp/dbt_logs"
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-"secure_postgres_password_123"}

# Create temporary directories
mkdir -p ${DBT_PROFILES_DIR}
mkdir -p ${DBT_TARGET_PATH}
mkdir -p ${DBT_LOG_PATH}

# Create a temporary profiles.yml for testing
cat > ${DBT_PROFILES_DIR}/profiles.yml <<EOF
job_dbt:
  target: docker
  outputs:
    docker:
      type: postgres
      host: postgres
      port: 5432
      user: job_etl_user
      password: ${POSTGRES_PASSWORD}
      dbname: job_etl
      schema: staging
      threads: 4
      keepalives_idle: 0
      connect_timeout: 10
      search_path: "staging,raw,marts,public"
EOF

echo "1. Testing dbt parse..."
${DBT_CMD} parse --project-dir ${DBT_PROJECT_DIR} --profiles-dir ${DBT_PROFILES_DIR} --target-path ${DBT_TARGET_PATH} --log-path ${DBT_LOG_PATH}
echo "✓ dbt parse passed"
echo ""

echo "2. Testing dbt compile..."
${DBT_CMD} compile --project-dir ${DBT_PROJECT_DIR} --profiles-dir ${DBT_PROFILES_DIR} --target-path ${DBT_TARGET_PATH} --log-path ${DBT_LOG_PATH}
echo "✓ dbt compile passed"
echo ""

echo "3. Testing dbt test..."
${DBT_CMD} test --project-dir ${DBT_PROJECT_DIR} --profiles-dir ${DBT_PROFILES_DIR} --target-path ${DBT_TARGET_PATH} --log-path ${DBT_LOG_PATH}
echo "✓ dbt test passed"
echo ""

echo "4. Testing dbt list..."
${DBT_CMD} list --project-dir ${DBT_PROJECT_DIR} --profiles-dir ${DBT_PROFILES_DIR} --target-path ${DBT_TARGET_PATH} --log-path ${DBT_LOG_PATH}
echo "✓ dbt list completed"
echo ""

# Clean up temporary profiles.yml
rm -rf ${DBT_PROFILES_DIR}
rm -rf ${DBT_TARGET_PATH}
rm -rf ${DBT_LOG_PATH}

echo "=== All dbt tests passed! ==="
echo "The dbt project skeleton is properly configured."

