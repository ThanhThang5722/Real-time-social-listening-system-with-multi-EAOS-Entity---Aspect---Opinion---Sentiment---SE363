"""
Test PySpark Service - Batch Prediction

Run this to verify PySpark service is working correctly
"""

import requests
import json

# PySpark service URL
PYSPARK_URL = "http://localhost:5001"

def test_health():
    """Test health endpoint"""
    print("=" * 60)
    print("1. Testing Health Endpoint")
    print("=" * 60)

    try:
        response = requests.get(f"{PYSPARK_URL}/health")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        if result.get('model') and result.get('spark'):
            print("✅ PySpark service is healthy!")
        else:
            print("❌ PySpark service has issues:")
            print(f"   Model loaded: {result.get('model')}")
            print(f"   Spark initialized: {result.get('spark')}")

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

    return True


def test_single_prediction():
    """Test single prediction"""
    print("\n" + "=" * 60)
    print("2. Testing Single Prediction")
    print("=" * 60)

    test_data = {
        "text": "MC dẫn rất tốt, chương trình vui nhộn"
    }

    try:
        response = requests.post(
            f"{PYSPARK_URL}/predict",
            json=test_data,
            timeout=30
        )

        print(f"Status: {response.status_code}")
        result = response.json()

        print(f"\nText: {result.get('text')}")
        print(f"Predictions:")

        predictions = result.get('predictions', [])
        if predictions:
            for i, pred in enumerate(predictions, 1):
                print(f"\n  {i}. Entity: {pred.get('entity')}")
                print(f"     Aspect: {pred.get('aspect')}")
                print(f"     Opinion: {pred.get('opinion')}")
                print(f"     Sentiment: {pred.get('sentiment')}")
                print(f"     Confidence: {pred.get('confidence')}")

            print(f"\n✅ Single prediction works! Found {len(predictions)} EAOS")
        else:
            print("⚠️  No predictions returned (might be low confidence)")

    except Exception as e:
        print(f"❌ Single prediction failed: {e}")
        return False

    return True


def test_batch_prediction():
    """Test batch prediction"""
    print("\n" + "=" * 60)
    print("3. Testing Batch Prediction")
    print("=" * 60)

    test_data = {
        "comments": [
            {"id": "1", "text": "MC dẫn rất tốt"},
            {"id": "2", "text": "Kịch bản hay, dàn cast ổn"},
            {"id": "3", "text": "Chương trình nhàm chán"},
            {"id": "4", "text": "Trấn Thành dẫn xuất sắc"},
            {"id": "5", "text": "Running Man Việt Nam rất vui"}
        ]
    }

    print(f"Testing with {len(test_data['comments'])} comments...")

    try:
        response = requests.post(
            f"{PYSPARK_URL}/predict/batch",
            json=test_data,
            timeout=60
        )

        print(f"Status: {response.status_code}")
        result = response.json()

        method = result.get('method', 'unknown')
        count = result.get('count', 0)

        print(f"\nMethod: {method}")
        print(f"Processed: {count} comments")

        # Show first result
        results = result.get('results', [])
        if results:
            first = results[0]
            print(f"\nFirst result:")
            print(f"  ID: {first.get('id')}")
            print(f"  Text: {first.get('text')}")
            print(f"  Predictions: {len(first.get('predictions', []))} EAOS")

            if first.get('predictions'):
                pred = first['predictions'][0]
                print(f"    - {pred.get('entity')} | {pred.get('aspect')} | {pred.get('opinion')} | {pred.get('sentiment')}")

            print(f"\n✅ Batch prediction works!")

            # Count total predictions
            total_preds = sum(len(r.get('predictions', [])) for r in results)
            print(f"   Total EAOS found: {total_preds}")
        else:
            print("❌ No results returned!")

    except Exception as e:
        print(f"❌ Batch prediction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PySpark Service Test")
    print("=" * 60)

    # Test health
    if not test_health():
        print("\n❌ Service is not healthy. Cannot proceed with tests.")
        return

    # Test single prediction
    test_single_prediction()

    # Test batch prediction
    test_batch_prediction()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
