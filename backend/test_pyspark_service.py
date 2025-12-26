"""
Test script for PySpark HTTP Service

Usage:
    python test_pyspark_service.py
"""

import requests
import json
import time

# Service URL
BASE_URL = "http://localhost:5001"

def test_health():
    """Test health endpoint"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()

        data = response.json()
        print(f"✅ Service is healthy")
        print(f"   Spark: {data.get('spark')}")
        print(f"   Model: {data.get('model')}")

        return True

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_single_prediction():
    """Test single prediction endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: Single Prediction")
    print("=" * 60)

    try:
        payload = {
            "text": "Chương trình rất hay, MC dẫn tốt!"
        }

        print(f"Input: {payload['text']}")

        response = requests.post(
            f"{BASE_URL}/predict",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        data = response.json()
        print(f"✅ Prediction successful")
        print(f"\nText: {data['text']}")
        print(f"Predictions: {json.dumps(data['predictions'], indent=2, ensure_ascii=False)}")

        return True

    except Exception as e:
        print(f"❌ Single prediction failed: {e}")
        return False

def test_batch_prediction():
    """Test batch prediction endpoint"""
    print("\n" + "=" * 60)
    print("TEST 3: Batch Prediction (PySpark)")
    print("=" * 60)

    try:
        payload = {
            "comments": [
                {
                    "id": "1",
                    "text": "Chương trình rất hay, nội dung cuốn hút!"
                },
                {
                    "id": "2",
                    "text": "MC dẫn tốt, giọng nói rõ ràng."
                },
                {
                    "id": "3",
                    "text": "Kịch bản chưa hay, hơi nhàm chán."
                }
            ]
        }

        print(f"Input: {len(payload['comments'])} comments")

        response = requests.post(
            f"{BASE_URL}/predict/batch",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        data = response.json()
        print(f"✅ Batch prediction successful")
        print(f"   Count: {data['count']}")

        for result in data['results']:
            print(f"\n   ID: {result['id']}")
            print(f"   Text: {result['text']}")
            print(f"   Predictions: {len(result['predictions'])} quadruples")

        return True

    except Exception as e:
        print(f"❌ Batch prediction failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("PySpark Service Test Suite")
    print("=" * 60)

    # Wait for service to be ready
    print("\nWaiting for service to start...")
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print("✅ Service is ready!")
                break
        except:
            pass

        if i < max_retries - 1:
            print(f"   Retry {i+1}/{max_retries}...")
            time.sleep(2)
    else:
        print("❌ Service failed to start in time")
        return

    # Run tests
    results = []
    results.append(("Health Check", test_health()))
    results.append(("Single Prediction", test_single_prediction()))
    results.append(("Batch Prediction", test_batch_prediction()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

if __name__ == "__main__":
    main()
