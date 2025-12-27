"""
Threshold-based Prediction DAG - Trigger when batch size reached

This DAG triggers when unlabeled comments reach a threshold:
- Checks MongoDB every minute
- Triggers processing when >= 100 unlabeled comments
- Runs same prediction pipeline as batch_prediction_dag

Use cases:
- Faster processing when many comments arrive quickly
- Complements time-based batch_prediction_dag
"""

from airflow import DAG
from airflow.sensors.python import PythonSensor
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
from pymongo import MongoClient

# Import task functions from batch_prediction_dag
import sys
sys.path.append('/opt/airflow/dags')
from batch_prediction_dag import (
    fetch_unlabeled_comments,
    predict_batch_via_pyspark,
    save_predictions_to_mongodb,
    generate_analytics_report,
    cleanup_temp_files
)

# ============================================================================
# Configuration
# ============================================================================

THRESHOLD = 100  # Trigger when >= 100 unlabeled comments

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

dag = DAG(
    'threshold_prediction',
    default_args=default_args,
    description='Trigger batch prediction when threshold reached',
    schedule_interval='*/1 * * * *',  # Check every 1 minute (for testing - change to */5 for production)
    start_date=days_ago(1),
    catchup=False,
    tags=['ml', 'prediction', 'threshold', 'sensor'],
)

# ============================================================================
# Sensor Function
# ============================================================================

def check_unlabeled_threshold(**context):
    """
    Check if unlabeled comments >= threshold

    Returns True to trigger pipeline, False to skip
    """
    from pymongo import MongoClient

    print(f"🔍 Checking unlabeled comments threshold (>= {THRESHOLD})...")

    # Connect to MongoDB
    client = MongoClient('mongodb://admin:admin123@mongodb:27017/')
    db = client['tv_analytics']
    collection = db['comments']

    # Count unlabeled
    count = collection.count_documents({
        '$or': [
            {'labels': {'$exists': False}},
            {'labels': {'$size': 0}}
        ]
    })

    print(f"   Found: {count} unlabeled comments")
    print(f"   Threshold: {THRESHOLD}")

    if count >= THRESHOLD:
        print(f"✅ Threshold reached! Triggering batch processing...")
        return True
    else:
        print(f"⏭️  Below threshold. Skipping...")
        return False


# ============================================================================
# Define Tasks
# ============================================================================

# Sensor: Wait until threshold is reached
threshold_sensor = PythonSensor(
    task_id='threshold_sensor',
    python_callable=check_unlabeled_threshold,
    poke_interval=60,  # Check every 60 seconds
    timeout=300,  # Give up after 5 minutes if threshold not reached
    mode='reschedule',  # Free up worker slot while waiting
    dag=dag,
)

# Same tasks as batch_prediction_dag
fetch_comments = PythonOperator(
    task_id='fetch_comments',
    python_callable=fetch_unlabeled_comments,
    dag=dag,
)

predict_batch = PythonOperator(
    task_id='predict_batch',
    python_callable=predict_batch_via_pyspark,
    dag=dag,
)

save_predictions = PythonOperator(
    task_id='save_predictions',
    python_callable=save_predictions_to_mongodb,
    dag=dag,
)

generate_report = PythonOperator(
    task_id='generate_report',
    python_callable=generate_analytics_report,
    dag=dag,
)

cleanup = PythonOperator(
    task_id='cleanup',
    python_callable=cleanup_temp_files,
    dag=dag,
)

# Define task flow
# Sensor triggers when threshold reached, then run pipeline
threshold_sensor >> fetch_comments >> predict_batch >> save_predictions >> generate_report >> cleanup
