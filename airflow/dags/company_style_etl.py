from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

def extract():
    print("Extract data from source")

def transform():
    print("Transform data")

def load():
    print("Load data to warehouse")

with DAG(
    dag_id="company_etl_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 3 * * *",
    catchup=False,
    default_args=default_args,
    tags=["etl", "core"]
) as dag:

    extract_task = PythonOperator(
        task_id="extract",
        python_callable=extract
    )

    transform_task = PythonOperator(
        task_id="transform",
        python_callable=transform
    )

    load_task = PythonOperator(
        task_id="load",
        python_callable=load
    )

    extract_task >> transform_task >> load_task
