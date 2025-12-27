"""
Debug Airflow DAG Execution

This script helps debug why Airflow is not calling PySpark
"""

from pymongo import MongoClient
import requests

# Configuration
MONGO_URL = "mongodb://admin:admin123@localhost:27017/"
PYSPARK_URL = "http://localhost:5001"
AIRFLOW_URL = "http://localhost:8080"

def check_mongodb():
    """Check MongoDB for unlabeled comments"""
    print("\n" + "=" * 70)
    print("  [1] Check MongoDB")
    print("=" * 70)

    try:
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        db = client['tv_analytics']
        collection = db['comments']

        # Test connection
        client.server_info()
        print("✅ MongoDB is accessible")

        # Count unlabeled
        unlabeled = collection.count_documents({
            '$or': [
                {'labels': {'$exists': False}},
                {'labels': {'$size': 0}}
            ]
        })

        # Count labeled
        labeled = collection.count_documents({
            'labels': {'$exists': True, '$ne': []}
        })

        print(f"\n📊 Comments in MongoDB:")
        print(f"   Unlabeled: {unlabeled}")
        print(f"   Labeled: {labeled}")
        print(f"   Total: {unlabeled + labeled}")

        if unlabeled == 0:
            print(f"\n⚠️  WARNING: No unlabeled comments!")
            print(f"   Airflow DAG will SKIP PySpark call if no unlabeled comments")
            print(f"\n   Fix: Run add_test_comments.py to add test data:")
            print(f"   python add_test_comments.py")
            return False

        # Show sample
        sample = collection.find_one({'labels': {'$size': 0}})
        if sample:
            print(f"\n📝 Sample unlabeled comment:")
            print(f"   ID: {sample['_id']}")
            print(f"   Text: {sample['text'][:60]}...")

        return True

    except Exception as e:
        print(f"❌ MongoDB Error: {e}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Check MongoDB is running: docker ps | grep mongodb")
        print(f"   2. Check MongoDB logs: docker compose logs mongodb")
        return False


def check_pyspark_service():
    """Check if PySpark service is running"""
    print("\n" + "=" * 70)
    print("  [2] Check PySpark Service")
    print("=" * 70)

    try:
        response = requests.get(f"{PYSPARK_URL}/health", timeout=5)
        data = response.json()

        print(f"✅ PySpark service is accessible")
        print(f"\n📊 PySpark service status:")
        print(f"   Status: {data.get('status')}")
        print(f"   Spark: {data.get('spark')}")
        print(f"   Model: {data.get('model')}")

        if not data.get('model'):
            print(f"\n⚠️  WARNING: Model is NOT loaded!")
            print(f"   Check PySpark logs: docker compose logs pyspark")
            return False

        if not data.get('spark'):
            print(f"\n⚠️  WARNING: Spark is NOT initialized!")
            return False

        return True

    except Exception as e:
        print(f"❌ PySpark Error: {e}")
        print(f"\n   Troubleshooting:")
        print(f"   1. Check PySpark is running: docker ps | grep pyspark")
        print(f"   2. Check PySpark logs: docker compose logs pyspark")
        print(f"   3. Start PySpark: docker compose up -d pyspark")
        return False


def check_airflow_dag():
    """Check Airflow DAG status"""
    print("\n" + "=" * 70)
    print("  [3] Check Airflow DAG")
    print("=" * 70)

    print(f"🔍 Checking Airflow DAG status...")
    print(f"\nManual checks needed:")
    print(f"   1. Open Airflow UI: http://localhost:8080")
    print(f"   2. Login: admin / admin")
    print(f"   3. Check 'batch_prediction' DAG:")
    print(f"      - Is it enabled (toggle ON)?")
    print(f"      - Any recent runs?")
    print(f"      - Any failed tasks?")

    print(f"\n📋 Check DAG logs:")
    print(f"   docker compose logs airflow-scheduler | grep batch_prediction")

    print(f"\n🔧 Trigger DAG manually:")
    print(f"   docker exec -it tv-analytics-airflow-scheduler \\")
    print(f"     airflow dags trigger batch_prediction")

    return True


def check_environment_variables():
    """Check if environment variables are set correctly"""
    print("\n" + "=" * 70)
    print("  [4] Check Environment Variables")
    print("=" * 70)

    print(f"🔍 Checking Airflow environment variables...")
    print(f"\nExpected variables in Airflow containers:")
    print(f"   PYSPARK_SERVICE_URL=http://pyspark:5001")
    print(f"   BACKEND_URL=http://host.docker.internal:8000")

    print(f"\n🔧 Verify variables:")
    print(f"   docker exec -it tv-analytics-airflow-scheduler env | grep PYSPARK")

    return True


def simulate_airflow_call():
    """Simulate what Airflow DAG does"""
    print("\n" + "=" * 70)
    print("  [5] Simulate Airflow DAG Call")
    print("=" * 70)

    print(f"🔍 Simulating Airflow DAG execution...")

    # Step 1: Fetch comments
    try:
        client = MongoClient(MONGO_URL)
        db = client['tv_analytics']
        collection = db['comments']

        comments = list(collection.find(
            {
                '$or': [
                    {'labels': {'$exists': False}},
                    {'labels': {'$size': 0}}
                ]
            },
            {'_id': 1, 'text': 1}
        ).limit(5))

        print(f"\n[STEP 1] Fetch comments: {len(comments)} unlabeled")

        if len(comments) == 0:
            print(f"   ⚠️  No unlabeled comments - DAG will SKIP PySpark call")
            return False

    except Exception as e:
        print(f"   ❌ Error fetching comments: {e}")
        return False

    # Step 2: Call PySpark
    try:
        import httpx

        request_data = {
            'comments': [
                {'id': str(c['_id']), 'text': c['text']}
                for c in comments
            ]
        }

        print(f"\n[STEP 2] Call PySpark service...")
        print(f"   URL: {PYSPARK_URL}/predict/batch")
        print(f"   Comments: {len(request_data['comments'])}")

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{PYSPARK_URL}/predict/batch",
                json=request_data
            )

            print(f"   Response: {response.status_code}")
            response.raise_for_status()
            result = response.json()

        print(f"\n   ✅ PySpark call succeeded!")
        print(f"   Method: {result.get('method')}")
        print(f"   Count: {result.get('count')}")

        if result.get('results'):
            first = result['results'][0]
            print(f"\n   📝 First prediction:")
            print(f"      Text: {first.get('text')[:50]}...")
            print(f"      Predictions: {len(first.get('predictions', []))} EAOS")

            if first.get('predictions'):
                pred = first['predictions'][0]
                print(f"      Sample: {pred.get('entity')} | {pred.get('aspect')} | {pred.get('opinion')} | {pred.get('sentiment')}")

        return True

    except Exception as e:
        print(f"   ❌ Error calling PySpark: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all checks"""
    print("\n" + "=" * 70)
    print("  DEBUG: Why Airflow is NOT calling PySpark")
    print("=" * 70)

    results = {}

    # Check 1: MongoDB
    results['MongoDB'] = check_mongodb()

    # Check 2: PySpark
    results['PySpark Service'] = check_pyspark_service()

    # Check 3: Airflow DAG
    results['Airflow DAG'] = check_airflow_dag()

    # Check 4: Environment Variables
    results['Environment Variables'] = check_environment_variables()

    # Check 5: Simulate call
    if results['MongoDB'] and results['PySpark Service']:
        results['Simulate Airflow Call'] = simulate_airflow_call()

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    all_passed = True
    for check, passed in results.items():
        if passed is not None:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status}: {check}")
            if not passed:
                all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All checks passed!")
        print("\nIf Airflow still doesn't call PySpark, check:")
        print("  1. Airflow DAG logs:")
        print("     docker compose logs airflow-scheduler | grep -A 20 batch_prediction")
        print("\n  2. Enable DAG debug logging in batch_prediction_dag.py")
        print("\n  3. Check Airflow UI for task failures")
    else:
        print("❌ Some checks failed - fix issues above")

    print("=" * 70)


if __name__ == "__main__":
    main()
