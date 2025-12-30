"""
Batch Prediction DAG - Near Real-time Comment Processing

This DAG runs batch predictions on accumulated comments:
1. Fetch comments from MongoDB (unlabeled ONLY)
2. Send to PySpark service for batch prediction
3. Save predictions back to MongoDB
4. Generate analytics report

Schedule: Every 15 minutes (Near Real-time)
Can also be triggered manually for immediate processing
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import json
import os

# ============================================================================
# DAG Configuration
# ============================================================================

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=3),
}

dag = DAG(
    'batch_prediction',
    default_args=default_args,
    description='Near real-time batch predictions using PySpark service',
    schedule_interval='*/1 * * * *',  # Every 1 minute (for testing - change to */15 for production)
    start_date=days_ago(1),
    catchup=False,
    tags=['ml', 'prediction', 'pyspark', 'batch', 'realtime'],
)

# ============================================================================
# Task Functions
# ============================================================================

def fetch_unlabeled_comments(**context):
    """
    Fetch comments without predictions from MongoDB

    Retrieves comments that:
    - Have no labels field, OR
    - Labels field is empty
    """
    from pymongo import MongoClient
    import json

    print("📊 Fetching unlabeled comments from MongoDB...")

    # Connect to MongoDB
    client = MongoClient('mongodb://admin:admin123@mongodb:27017/')
    db = client['tv_analytics']
    collection = db['comments']

    # Query unlabeled comments ONLY (exclude already attempted comments with predicted_at)
    comments = list(collection.find(
        {
            '$and': [
                {
                    '$or': [
                        {'labels': {'$exists': False}},
                        {'labels': {'$size': 0}}
                    ]
                },
                {'predicted_at': {'$exists': False}}  # Exclude previously attempted comments
            ]
        },
        {'_id': 1, 'text': 1}
    ).sort('created_at', -1).limit(5))  # Process 5 comments per run (every 1 min = ~300/hour) - uses direct inference, sorted by creation time (NEWEST first for testing)

    print(f"✅ Found {len(comments)} unlabeled comments")

    if len(comments) == 0:
        print("⏭️  No unlabeled comments found. Skipping...")
        return []

    # Convert ObjectId to string for JSON serialization
    for comment in comments:
        comment['_id'] = str(comment['_id'])

    # Save to file
    output_path = '/tmp/unlabeled_comments.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)

    # Push to XCom
    context['task_instance'].xcom_push(key='num_comments', value=len(comments))
    context['task_instance'].xcom_push(key='comment_ids', value=[str(c['_id']) for c in comments])

    return comments


def predict_batch_via_pyspark(**context):
    """
    Send batch to PySpark service for prediction

    Uses /predict/batch endpoint which:
    - Uses direct inference for batch < 10
    - Uses PySpark PandasUDF for batch >= 10
    """
    import httpx

    comments = context['task_instance'].xcom_pull(task_ids='fetch_comments')

    if not comments or len(comments) == 0:
        print("⏭️  No comments to predict")
        return []

    print(f"🚀 Sending {len(comments)} comments to PySpark service...")

    # PySpark service URL
    pyspark_url = os.getenv('PYSPARK_SERVICE_URL', 'http://pyspark:5001')
    print(f"   PySpark URL: {pyspark_url}")

    # Prepare request
    request_data = {
        'comments': [
            {'id': str(c['_id']), 'text': c['text']}
            for c in comments
        ]
    }

    print(f"   Sample request: {request_data['comments'][:2]}")  # Show first 2

    # Call PySpark service
    try:
        with httpx.Client(timeout=300.0) as client:
            print(f"   Calling {pyspark_url}/predict/batch...")
            response = client.post(
                f"{pyspark_url}/predict/batch",
                json=request_data
            )

            print(f"   Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()

        method = result.get('method', 'unknown')
        count = result.get('count', 0)

        # DEBUG: Show first prediction
        if result.get('results') and len(result['results']) > 0:
            first_pred = result['results'][0]
            print(f"\n📝 First prediction sample:")
            print(f"   Text: {first_pred.get('text', 'N/A')}")
            print(f"   Predictions count: {len(first_pred.get('predictions', []))}")
            if first_pred.get('predictions'):
                print(f"   First prediction: {first_pred['predictions'][0]}")
        else:
            print(f"⚠️  WARNING: No predictions returned!")

        print(f"✅ Predictions completed using method: {method}")
        print(f"   Processed: {count} comments")

        # Save results
        output_path = '/tmp/predictions.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result['results'], f, ensure_ascii=False, indent=2)

        return result['results']

    except Exception as e:
        print(f"❌ Prediction failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def save_predictions_to_mongodb(**context):
    """
    Save predictions back to MongoDB

    Updates each comment document with predictions
    """
    from pymongo import MongoClient
    from bson import ObjectId

    predictions = context['task_instance'].xcom_pull(task_ids='predict_batch')

    if not predictions:
        print("⏭️  No predictions to save")
        return 0

    print(f"💾 Saving {len(predictions)} predictions to MongoDB...")

    # DEBUG: Show first prediction
    if len(predictions) > 0:
        print(f"\n📝 First prediction to save:")
        print(f"   ID: {predictions[0].get('id', 'N/A')}")
        print(f"   Text: {predictions[0].get('text', 'N/A')[:50]}...")
        print(f"   Predictions: {predictions[0].get('predictions', [])}")

    # Connect to MongoDB
    client = MongoClient('mongodb://admin:admin123@mongodb:27017/')
    db = client['tv_analytics']
    collection = db['comments']

    # Update documents
    updated_count = 0
    empty_prediction_count = 0

    for pred in predictions:
        comment_id = pred['id']
        labels = pred['predictions']

        # DEBUG: Track empty predictions
        if not labels or len(labels) == 0:
            empty_prediction_count += 1
            print(f"⚠️  Empty prediction for comment {comment_id}: {pred.get('text', 'N/A')[:50]}...")
            # Mark as attempted with timestamp to avoid re-processing
            print(f"   ⏭️  Marking as attempted (empty prediction)")
            collection.update_one(
                {'_id': ObjectId(comment_id)},
                {'$set': {'predicted_at': datetime.now(), 'labels': []}}
            )
            continue

        # Convert labels format
        formatted_labels = []
        for label in labels:
            formatted_labels.append({
                'entity': label['entity'],
                'aspect': label['aspect'],
                'opinion': label['opinion'],
                'sentiment': label['sentiment'],
                'confidence': label.get('confidence', 0.0)
            })

        # Update document
        result = collection.update_one(
            {'_id': ObjectId(comment_id)},
            {
                '$set': {
                    'labels': formatted_labels,
                    'predicted_at': datetime.now()
                }
            }
        )

        if result.modified_count > 0:
            updated_count += 1

    print(f"✅ Updated {updated_count} documents in MongoDB")
    if empty_prediction_count > 0:
        print(f"⚠️  {empty_prediction_count} comments had empty predictions (low confidence or no EAOS found)")

    # Push comment IDs to XCom for notification
    context['task_instance'].xcom_push(key='updated_comment_ids', value=[pred['id'] for pred in predictions])

    return updated_count


def notify_backend_websocket(**context):
    """
    Notify Backend to broadcast WebSocket message about new predictions

    Calls Backend API endpoint to trigger real-time notification
    to all connected WebSocket clients
    """
    import httpx

    updated_count = context['task_instance'].xcom_pull(task_ids='save_predictions')
    comment_ids = context['task_instance'].xcom_pull(task_ids='save_predictions', key='updated_comment_ids')

    if not updated_count or updated_count == 0:
        print("⏭️  No updates to notify")
        return False

    print(f"📢 Notifying Backend about {updated_count} new predictions...")

    # Backend URL
    backend_url = os.getenv('BACKEND_URL', 'http://host.docker.internal:8000')
    notify_endpoint = f"{backend_url}/api/notify/predictions"

    print(f"   Calling: {notify_endpoint}")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                notify_endpoint,
                json={'comment_ids': comment_ids or []}
            )

            print(f"   Response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                broadcasted_to = result.get('broadcasted_to', 0)
                print(f"✅ Notified {broadcasted_to} WebSocket clients")
                return True
            else:
                print(f"⚠️  Notification failed with status {response.status_code}")
                return False

    except Exception as e:
        print(f"⚠️  Failed to notify Backend: {e}")
        # Don't fail the task - notification is optional
        return False


def generate_analytics_report(**context):
    """
    Generate analytics report after batch prediction

    Calculates:
    - Sentiment distribution
    - Top entities
    - Top aspects
    """
    from pymongo import MongoClient
    from collections import Counter

    print("📊 Generating analytics report...")

    # Connect to MongoDB
    client = MongoClient('mongodb://admin:admin123@mongodb:27017/')
    db = client['tv_analytics']
    collection = db['comments']

    # Get all labeled comments
    comments = list(collection.find({'labels': {'$exists': True, '$ne': []}}))

    if not comments:
        print("⏭️  No labeled comments for analytics")
        return {}

    # Calculate analytics
    sentiments = Counter()
    entities = Counter()
    aspects = Counter()

    for comment in comments:
        for label in comment['labels']:
            sentiments[label['sentiment']] += 1
            entities[label['entity']] += 1
            aspects[label['aspect']] += 1

    report = {
        'timestamp': datetime.now().isoformat(),
        'total_comments': len(comments),
        'sentiment_distribution': dict(sentiments),
        'top_entities': dict(entities.most_common(10)),
        'top_aspects': dict(aspects.most_common(10))
    }

    # Save report
    report_path = '/tmp/analytics_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("✅ Analytics report generated:")
    print(f"   Total comments: {report['total_comments']}")
    print(f"   Sentiments: {report['sentiment_distribution']}")

    return report


def cleanup_temp_files(**context):
    """Clean up temporary files"""
    import os

    temp_files = [
        '/tmp/unlabeled_comments.json',
        '/tmp/predictions.json',
        '/tmp/analytics_report.json'
    ]

    for file_path in temp_files:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️  Removed {file_path}")

    print("✅ Cleanup completed")
    return True


# ============================================================================
# Define Tasks
# ============================================================================

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

notify_websocket = PythonOperator(
    task_id='notify_websocket',
    python_callable=notify_backend_websocket,
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
fetch_comments >> predict_batch >> save_predictions >> notify_websocket >> generate_report >> cleanup
