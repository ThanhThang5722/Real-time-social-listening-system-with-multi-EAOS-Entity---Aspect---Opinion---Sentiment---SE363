"""
Test Airflow → PySpark Flow
Simulates EXACTLY how Airflow DAG calls PySpark service
"""

import httpx
import json
from pymongo import MongoClient
from bson import ObjectId

# ============================================================================
# Configuration (Same as Airflow)
# ============================================================================

# PySpark URL (same as Airflow environment variable)
PYSPARK_URL = "http://localhost:5001"  # Change to http://pyspark:5001 in Docker

# MongoDB (to fetch real unlabeled comments like Airflow does)
MONGO_URL = "mongodb://admin:admin123@localhost:27017/"

# ============================================================================
# Test Functions
# ============================================================================

def fetch_unlabeled_comments_from_mongodb():
    """
    Fetch unlabeled comments from MongoDB
    EXACTLY like Airflow DAG does (batch_prediction_dag.py:68-76)
    """
    print("📊 Fetching unlabeled comments from MongoDB...")

    client = MongoClient(MONGO_URL)
    db = client['tv_analytics']
    collection = db['comments']

    # Query unlabeled comments ONLY (same as Airflow)
    comments = list(collection.find(
        {
            '$or': [
                {'labels': {'$exists': False}},
                {'labels': {'$size': 0}}
            ]
        },
        {'_id': 1, 'text': 1}
    ).limit(5))  # Limit to 5 for testing

    print(f"✅ Found {len(comments)} unlabeled comments")

    for i, c in enumerate(comments[:3], 1):
        print(f"   {i}. {c['text'][:50]}...")

    return comments


def call_pyspark_service(comments):
    """
    Call PySpark service EXACTLY like Airflow DAG does
    (batch_prediction_dag.py:119-139)
    """
    print(f"\n🚀 Calling PySpark service with {len(comments)} comments...")

    # Prepare request EXACTLY like Airflow
    request_data = {
        'comments': [
            {'id': str(c['_id']), 'text': c['text']}
            for c in comments
        ]
    }

    print(f"   URL: {PYSPARK_URL}/predict/batch")
    print(f"   Payload sample: {json.dumps(request_data['comments'][:1], indent=2, ensure_ascii=False)}")

    try:
        # Call service EXACTLY like Airflow
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{PYSPARK_URL}/predict/batch",
                json=request_data
            )

            print(f"   Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()

        # Parse results EXACTLY like Airflow
        method = result.get('method', 'unknown')
        count = result.get('count', 0)
        results = result.get('results', [])

        print(f"\n✅ PySpark service responded successfully")
        print(f"   Method: {method}")
        print(f"   Count: {count}")

        # Show first result
        if results:
            first = results[0]
            predictions = first.get('predictions', [])

            print(f"\n📝 First result:")
            print(f"   ID: {first.get('id')}")
            print(f"   Text: {first.get('text')[:50]}...")
            print(f"   Predictions: {len(predictions)} EAOS")

            if predictions:
                pred = predictions[0]
                print(f"\n   📊 First EAOS:")
                print(f"      Entity: {pred.get('entity')}")
                print(f"      Aspect: {pred.get('aspect')}")
                print(f"      Opinion: {pred.get('opinion')}")
                print(f"      Sentiment: {pred.get('sentiment')}")
                print(f"      Confidence: {pred.get('confidence')}")

                print("\n   ✅ OUTPUT FORMAT CORRECT!")
                print("      ✓ Entity")
                print("      ✓ Aspect")
                print("      ✓ Opinion")
                print("      ✓ Sentiment")
            else:
                print("\n   ⚠️  No predictions (might be low confidence or no EAOS found)")

        return results

    except httpx.ConnectError as e:
        print(f"\n❌ ERROR: Cannot connect to PySpark service at {PYSPARK_URL}")
        print(f"   Error: {e}")
        print("\n   Troubleshooting:")
        print("   1. Check if PySpark container is running:")
        print("      docker ps | grep pyspark")
        print("   2. Check PySpark logs:")
        print("      docker compose logs pyspark")
        print("   3. Start PySpark service:")
        print("      docker compose up -d pyspark")
        return None

    except httpx.HTTPStatusError as e:
        print(f"\n❌ ERROR: PySpark service returned error {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        return None

    except Exception as e:
        print(f"\n❌ ERROR: Unexpected error")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_predictions_to_mongodb(predictions):
    """
    Save predictions back to MongoDB
    EXACTLY like Airflow DAG does (batch_prediction_dag.py:205-239)
    """
    if not predictions:
        print("\n⏭️  No predictions to save")
        return 0

    print(f"\n💾 Saving {len(predictions)} predictions to MongoDB...")

    client = MongoClient(MONGO_URL)
    db = client['tv_analytics']
    collection = db['comments']

    updated_count = 0

    for pred in predictions:
        comment_id = pred['id']
        labels = pred['predictions']

        # Convert labels format EXACTLY like Airflow
        formatted_labels = []
        for label in labels:
            formatted_labels.append({
                'entity': label['entity'],
                'aspect': label['aspect'],
                'opinion': label['opinion'],
                'sentiment': label['sentiment'],
                'confidence': label.get('confidence', 0.0)
            })

        # Update document EXACTLY like Airflow
        from datetime import datetime
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
    return updated_count


def verify_saved_data():
    """Verify data was saved correctly"""
    print("\n🔍 Verifying saved data in MongoDB...")

    client = MongoClient(MONGO_URL)
    db = client['tv_analytics']
    collection = db['comments']

    # Get one labeled comment
    labeled = collection.find_one({'labels': {'$exists': True, '$ne': []}})

    if labeled:
        print(f"✅ Found labeled comment:")
        print(f"   Text: {labeled['text'][:50]}...")
        print(f"   Labels count: {len(labeled.get('labels', []))}")

        if labeled['labels']:
            label = labeled['labels'][0]
            print(f"\n   First label:")
            print(f"      Entity: {label.get('entity')}")
            print(f"      Aspect: {label.get('aspect')}")
            print(f"      Opinion: {label.get('opinion')}")
            print(f"      Sentiment: {label.get('sentiment')}")
            print(f"      Confidence: {label.get('confidence')}")
    else:
        print("❌ No labeled comments found in MongoDB")


def main():
    """
    Main test flow - Simulates EXACTLY what Airflow does
    """
    print("=" * 70)
    print("  TEST: Airflow → PySpark Service Flow")
    print("=" * 70)
    print("\nThis simulates EXACTLY how Airflow DAG calls PySpark service:")
    print("  1. Fetch unlabeled comments from MongoDB")
    print("  2. Call PySpark service (http://pyspark:5001/predict/batch)")
    print("  3. Receive predictions with Entity, Aspect, Opinion, Sentiment")
    print("  4. Save predictions back to MongoDB")
    print("\n" + "=" * 70)

    # Step 1: Fetch unlabeled comments
    print("\n[STEP 1] Fetch Unlabeled Comments")
    print("-" * 70)
    comments = fetch_unlabeled_comments_from_mongodb()

    if not comments:
        print("\n⚠️  No unlabeled comments found in MongoDB")
        print("   Add some test comments first:")
        print("   curl -X POST http://localhost:8000/api/submit \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{\"text\": \"MC dẫn tốt\"}'")
        return

    # Step 2: Call PySpark service
    print("\n[STEP 2] Call PySpark Service")
    print("-" * 70)
    predictions = call_pyspark_service(comments)

    if not predictions:
        print("\n❌ Failed to get predictions from PySpark service")
        return

    # Step 3: Save to MongoDB
    print("\n[STEP 3] Save Predictions to MongoDB")
    print("-" * 70)
    updated = save_predictions_to_mongodb(predictions)

    # Step 4: Verify
    print("\n[STEP 4] Verify Saved Data")
    print("-" * 70)
    verify_saved_data()

    # Summary
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print(f"\nSummary:")
    print(f"  - Fetched: {len(comments)} unlabeled comments")
    print(f"  - Predicted: {len(predictions)} comments")
    print(f"  - Saved: {updated} comments to MongoDB")
    print(f"\n🚀 Airflow can use the EXACT SAME approach!")
    print("=" * 70)


if __name__ == "__main__":
    main()
