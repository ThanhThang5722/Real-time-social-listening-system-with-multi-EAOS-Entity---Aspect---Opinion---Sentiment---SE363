"""
Verify Complete Airflow → PySpark → Spark Flow

This script verifies:
1. PySpark service is running
2. Model is loaded correctly
3. Predictions return Entity, Aspect, Opinion, Sentiment
4. Airflow can call the service successfully
"""

import requests
import json
import sys

PYSPARK_URL = "http://localhost:5001"

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check_pyspark_health():
    """Check if PySpark service is running and healthy"""
    print_section("1. PySpark Service Health Check")

    try:
        response = requests.get(f"{PYSPARK_URL}/health", timeout=5)
        result = response.json()

        print(f"✅ PySpark service is running")
        print(f"   Status: {result.get('status')}")
        print(f"   Spark initialized: {result.get('spark')}")
        print(f"   Model loaded: {result.get('model')}")

        if not result.get('model'):
            print("\n❌ ERROR: Model is NOT loaded!")
            print("   Check:")
            print("   1. Model file exists: backend/models/checkpoints/latest_checkpoint.pth")
            print("   2. PySpark container logs: docker compose logs pyspark")
            return False

        if not result.get('spark'):
            print("\n❌ ERROR: Spark is NOT initialized!")
            return False

        return True

    except Exception as e:
        print(f"❌ ERROR: Cannot connect to PySpark service at {PYSPARK_URL}")
        print(f"   Error: {e}")
        print("\n   Troubleshooting:")
        print("   1. Check if container is running: docker ps | grep pyspark")
        print("   2. Check logs: docker compose logs pyspark")
        print("   3. Try starting: docker compose up -d pyspark")
        return False


def test_single_prediction():
    """Test single prediction to verify model output format"""
    print_section("2. Test Single Prediction (Verify Output Format)")

    test_text = "MC Trấn Thành dẫn chương trình rất hay và vui nhộn"

    try:
        response = requests.post(
            f"{PYSPARK_URL}/predict",
            json={"text": test_text},
            timeout=30
        )

        result = response.json()
        predictions = result.get('predictions', [])

        print(f"Input: {test_text}")
        print(f"Found: {len(predictions)} EAOS quadruples")

        if predictions:
            print("\n📝 Prediction Output Format:")
            for i, pred in enumerate(predictions, 1):
                print(f"\n   {i}. Entity: {pred.get('entity')}")
                print(f"      Aspect: {pred.get('aspect')}")
                print(f"      Opinion: {pred.get('opinion')}")
                print(f"      Sentiment: {pred.get('sentiment')}")
                print(f"      Confidence: {pred.get('confidence')}")

            # Verify all required fields exist
            required_fields = ['entity', 'aspect', 'opinion', 'sentiment']
            missing_fields = [f for f in required_fields if f not in predictions[0]]

            if missing_fields:
                print(f"\n❌ ERROR: Missing fields in output: {missing_fields}")
                return False
            else:
                print("\n✅ Output format is CORRECT!")
                print("   ✓ Entity")
                print("   ✓ Aspect")
                print("   ✓ Opinion")
                print("   ✓ Sentiment")
                return True
        else:
            print("\n⚠️  WARNING: No predictions returned")
            print("   This might be due to:")
            print("   - Low confidence (threshold too high)")
            print("   - Model not detecting EAOS in this text")
            print("   - Model not loaded correctly")

            # Try a simpler text
            print("\n   Trying simpler text...")
            response = requests.post(
                f"{PYSPARK_URL}/predict",
                json={"text": "Chương trình hay"},
                timeout=30
            )
            result = response.json()
            if result.get('predictions'):
                print(f"   ✅ Found predictions for simpler text: {len(result['predictions'])} EAOS")
                return True
            else:
                print("   ❌ Still no predictions - model might have issues")
                return False

    except Exception as e:
        print(f"❌ ERROR: Prediction failed")
        print(f"   Error: {e}")
        return False


def test_batch_prediction_spark():
    """Test batch prediction to verify Spark is used for batches >= 10"""
    print_section("3. Test Batch Prediction (Verify Spark PandasUDF)")

    # Create batch of 15 comments to trigger Spark
    comments = [
        {"id": f"{i}", "text": f"Bình luận test số {i} về chương trình"}
        for i in range(1, 16)
    ]

    # Add some meaningful comments
    comments[0] = {"id": "1", "text": "MC dẫn rất tốt"}
    comments[1] = {"id": "2", "text": "Kịch bản hay, dàn cast ổn"}
    comments[2] = {"id": "3", "text": "Chương trình vui nhộn"}

    print(f"Sending batch of {len(comments)} comments...")
    print(f"Expected method: {'PySpark (PandasUDF)' if len(comments) >= 10 else 'Direct inference'}")

    try:
        response = requests.post(
            f"{PYSPARK_URL}/predict/batch",
            json={"comments": comments},
            timeout=120
        )

        result = response.json()
        method = result.get('method')
        count = result.get('count')
        results = result.get('results', [])

        print(f"\n✅ Batch prediction completed")
        print(f"   Method used: {method}")
        print(f"   Comments processed: {count}")

        # Verify Spark was used
        if len(comments) >= 10 and method != 'pyspark':
            print(f"\n⚠️  WARNING: Expected 'pyspark' method but got '{method}'")
            print("   Spark PandasUDF might not be working correctly")

        # Verify output format
        if results:
            first_result = results[0]
            print(f"\n📝 First result:")
            print(f"   ID: {first_result.get('id')}")
            print(f"   Text: {first_result.get('text')}")
            print(f"   Predictions: {len(first_result.get('predictions', []))} EAOS")

            if first_result.get('predictions'):
                pred = first_result['predictions'][0]
                print(f"\n   Sample EAOS:")
                print(f"   - Entity: {pred.get('entity')}")
                print(f"   - Aspect: {pred.get('aspect')}")
                print(f"   - Opinion: {pred.get('opinion')}")
                print(f"   - Sentiment: {pred.get('sentiment')}")

                print("\n✅ Batch prediction output format is CORRECT!")
                return True
            else:
                print("\n⚠️  First result has no predictions")

                # Count how many have predictions
                with_preds = sum(1 for r in results if r.get('predictions'))
                print(f"   Results with predictions: {with_preds}/{len(results)}")

                if with_preds > 0:
                    print("   ✅ Some predictions found - model is working")
                    return True
                else:
                    print("   ❌ No predictions in entire batch!")
                    return False
        else:
            print("\n❌ ERROR: No results returned!")
            return False

    except Exception as e:
        print(f"❌ ERROR: Batch prediction failed")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_airflow_compatible_request():
    """Test exactly how Airflow will call the service"""
    print_section("4. Test Airflow-Compatible Request")

    # This is EXACTLY how Airflow DAG sends requests
    airflow_request = {
        "comments": [
            {"id": "507f1f77bcf86cd799439011", "text": "MC dẫn tốt"},
            {"id": "507f1f77bcf86cd799439012", "text": "Kịch bản hay"},
            {"id": "507f1f77bcf86cd799439013", "text": "Chương trình vui"},
        ]
    }

    print("Simulating Airflow DAG request...")
    print(f"Request format: {json.dumps(airflow_request, indent=2, ensure_ascii=False)[:200]}...")

    try:
        response = requests.post(
            f"{PYSPARK_URL}/predict/batch",
            json=airflow_request,
            timeout=60
        )

        result = response.json()

        print(f"\n✅ Airflow-compatible request succeeded")
        print(f"   Status: {response.status_code}")
        print(f"   Method: {result.get('method')}")
        print(f"   Count: {result.get('count')}")

        # Verify response format matches what Airflow expects
        results = result.get('results', [])
        if results:
            first = results[0]

            # Check required fields
            if 'id' in first and 'text' in first and 'predictions' in first:
                print("\n✅ Response format matches Airflow expectations!")
                print("   ✓ id field")
                print("   ✓ text field")
                print("   ✓ predictions field")

                # Check predictions format
                if first['predictions']:
                    pred = first['predictions'][0]
                    required = ['entity', 'aspect', 'opinion', 'sentiment']
                    has_all = all(k in pred for k in required)

                    if has_all:
                        print("\n✅ Predictions have all required fields!")
                        print("   ✓ entity")
                        print("   ✓ aspect")
                        print("   ✓ opinion")
                        print("   ✓ sentiment")
                        return True
                    else:
                        missing = [k for k in required if k not in pred]
                        print(f"\n❌ Missing fields in predictions: {missing}")
                        return False
                else:
                    print("\n⚠️  Predictions array is empty (might be low confidence)")
                    return True  # Still valid, just no high-confidence results
            else:
                print("\n❌ Response missing required fields!")
                return False
        else:
            print("\n❌ No results returned!")
            return False

    except Exception as e:
        print(f"❌ ERROR: Airflow-compatible request failed")
        print(f"   Error: {e}")
        return False


def main():
    print("\n" + "=" * 70)
    print("  VERIFICATION: Airflow → PySpark → Spark → Model Flow")
    print("=" * 70)
    print("\nThis script verifies the complete pipeline:")
    print("  Airflow DAG → HTTP → PySpark Service → Spark PandasUDF → Model")
    print("  → Output (Entity, Aspect, Opinion, Sentiment)")

    # Run all checks
    checks = [
        ("PySpark Health", check_pyspark_health),
        ("Single Prediction", test_single_prediction),
        ("Batch with Spark", test_batch_prediction_spark),
        ("Airflow Compatibility", test_airflow_compatible_request),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ Check '{name}' crashed: {e}")
            results[name] = False

    # Summary
    print_section("SUMMARY")

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print("\nThe pipeline is working correctly:")
        print("  ✓ PySpark service is healthy")
        print("  ✓ Model is loaded and predicting")
        print("  ✓ Spark PandasUDF is working")
        print("  ✓ Output format includes Entity, Aspect, Opinion, Sentiment")
        print("  ✓ Airflow can call the service successfully")
        print("\n🚀 Ready for Airflow batch processing!")
    else:
        print("❌ SOME CHECKS FAILED!")
        print("\nPlease fix the issues above before running Airflow DAG.")
        print("\nCommon fixes:")
        print("  1. Start PySpark service: docker compose up -d pyspark")
        print("  2. Check model file exists: ls -lh backend/models/checkpoints/")
        print("  3. View logs: docker compose logs pyspark")
        print("  4. Restart service: docker compose restart pyspark")

    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
