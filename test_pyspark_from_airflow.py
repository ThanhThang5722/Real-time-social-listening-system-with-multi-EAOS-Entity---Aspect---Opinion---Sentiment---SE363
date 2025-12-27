"""
Test PySpark call from Airflow environment context
"""

from pymongo import MongoClient
import httpx
import json

def test_pyspark_call():
    """Test what Airflow predict_batch task does"""

    # Step 1: Fetch comments from MongoDB
    print("\n[STEP 1] Fetching unlabeled comments from MongoDB...")
    client = MongoClient('mongodb://admin:admin123@localhost:27017/')
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

    print(f"[OK] Found {len(comments)} unlabeled comments")

    if len(comments) == 0:
        print("[ERROR] No unlabeled comments to test with")
        return

    # Convert ObjectId to string
    for comment in comments:
        comment['_id'] = str(comment['_id'])

    # Step 2: Call PySpark service
    print("\n[STEP 2] Calling PySpark service...")
    pyspark_url = 'http://localhost:5001'

    request_data = {
        'comments': [
            {'id': str(c['_id']), 'text': c['text']}
            for c in comments
        ]
    }

    print(f"   URL: {pyspark_url}/predict/batch")
    print(f"   Comments: {len(request_data['comments'])}")
    print(f"   Sample ID: {request_data['comments'][0]['id']}")

    try:
        with httpx.Client(timeout=60.0) as http_client:
            response = http_client.post(
                f"{pyspark_url}/predict/batch",
                json=request_data
            )

            print(f"\n   Response status: {response.status_code}")

            if response.status_code != 200:
                print(f"   Response body: {response.text}")
                response.raise_for_status()

            result = response.json()

            print(f"\n[OK] PySpark call succeeded!")
            print(f"   Method: {result.get('method')}")
            print(f"   Count: {result.get('count')}")

            if result.get('results') and len(result['results']) > 0:
                first = result['results'][0]
                print(f"\n   [INFO] First prediction:")
                print(f"      Text: {first.get('text')[:50]}...")
                print(f"      Predictions: {len(first.get('predictions', []))} EAOS")

                if first.get('predictions'):
                    pred = first['predictions'][0]
                    print(f"      Sample: {pred.get('entity')} | {pred.get('aspect')} | {pred.get('opinion')} | {pred.get('sentiment')}")
            else:
                print(f"\n[WARNING] No predictions in response")
                print(f"   Response: {json.dumps(result, indent=2)}")

    except httpx.HTTPStatusError as e:
        print(f"\n[ERROR] HTTP Error: {e}")
        print(f"   Response: {e.response.text}")
        raise
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    test_pyspark_call()
