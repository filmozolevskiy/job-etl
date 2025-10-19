"""
Example DAG for Job-ETL project.
This is a simple DAG to verify Airflow setup is working correctly.
"""
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils import timezone


default_args = {
    'owner': 'job-etl',
    'depends_on_past': False,
    'start_date': timezone.datetime(2025, 10, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def print_hello():
    """Simple Python function to verify PythonOperator works."""
    print("Hello from Job-ETL Example DAG!")
    print("Airflow setup is working correctly.")
    return "success"


def check_database_connection():
    """Verify database connection is available."""
    from airflow.hooks.base import BaseHook
    try:
        conn = BaseHook.get_connection('postgres_default')
        print(f"Database connection found: {conn.host}")
        print("Connection test successful!")
        return "connection_ok"
    except Exception as e:
        print(f"Connection test failed: {e}")
        raise


with DAG(
    'example_dag',
    default_args=default_args,
    description='Example DAG to verify Airflow setup',
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=['example', 'setup', 'test'],
) as dag:

    # Task 1: Simple bash command
    start_task = BashOperator(
        task_id='start',
        bash_command='echo "Starting example DAG execution..."',
    )

    # Task 2: Python function
    hello_task = PythonOperator(
        task_id='say_hello',
        python_callable=print_hello,
    )

    # Task 3: Check database connection
    db_check_task = PythonOperator(
        task_id='check_database',
        python_callable=check_database_connection,
    )

    # Task 4: Complete
    end_task = BashOperator(
        task_id='end',
        bash_command='echo "Example DAG completed successfully!"',
    )

    # Define task dependencies
    start_task >> hello_task >> db_check_task >> end_task

