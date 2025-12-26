"""
Quick test script for Spark PandasUDF with EAOS model

Usage:
    python test_spark_udf.py
"""

import sys
from pathlib import Path

# Add ml directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_model_loading():
    """Test 1: Model loading from checkpoint"""
    print("=" * 70)
    print("TEST 1: Model Loading")
    print("=" * 70)

    from ml.eaos_model import load_model

    model_dir = "./models/checkpoints"

    try:
        model, tokenizer, config = load_model(model_dir)
        print("✅ Model loaded successfully!")
        print(f"   Model type: {type(model).__name__}")
        print(f"   Config: {config['model_name']}")
        print(f"   Best epoch: {config.get('best_epoch', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_inference():
    """Test 2: Single inference"""
    print("\n" + "=" * 70)
    print("TEST 2: Inference")
    print("=" * 70)

    from ml.eaos_model import create_inference

    try:
        inference = create_inference("./models/checkpoints", confidence_threshold=0.3)
        print("✅ Inference service created")

        # Test prediction
        test_text = "Chương trình rất hay và bổ ích!"
        print(f"\nTest text: {test_text}")

        predictions = inference.predict(test_text)
        print(f"✅ Predictions: {len(predictions)} labels found")

        for i, pred in enumerate(predictions, 1):
            print(f"\n   Label {i}:")
            print(f"      Entity: {pred['entity']}")
            print(f"      Aspect: {pred['aspect']}")
            print(f"      Opinion: {pred['opinion']}")
            print(f"      Sentiment: {pred['sentiment']}")
            print(f"      Confidence: {pred['confidence']}")

        return True
    except Exception as e:
        print(f"❌ Inference failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_spark_udf():
    """Test 3: Spark PandasUDF (requires Spark running)"""
    print("\n" + "=" * 70)
    print("TEST 3: Spark PandasUDF")
    print("=" * 70)

    try:
        from pyspark.sql import SparkSession

        # Try to create Spark session
        spark = SparkSession.builder \
            .appName("EAOS-Test") \
            .master("local[*]") \
            .config("spark.driver.memory", "2g") \
            .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
            .getOrCreate()

        print("✅ Spark session created (local mode)")

        # Import UDF creator
        from ml.spark_inference import create_eaos_udf

        # Create UDF
        eaos_udf = create_eaos_udf("./models/checkpoints")
        print("✅ PandasUDF created")

        # Test with sample data
        from pyspark.sql.functions import col

        sample_data = [
            ("1", "Chương trình rất hay!"),
            ("2", "MC dẫn tốt, kịch bản cuốn"),
            ("3", "Mùa này không hay bằng mùa trước"),
        ]

        df = spark.createDataFrame(sample_data, ["id", "text"])
        print("\n📊 Sample data:")
        df.show(truncate=False)

        # Apply UDF
        print("\n⚡ Applying PandasUDF...")
        result_df = df.withColumn("predictions", eaos_udf(col("text")))

        print("\n📊 Results:")
        result_df.show(truncate=False)

        spark.stop()
        print("\n✅ Spark PandasUDF test passed!")
        return True

    except ImportError as e:
        print(f"⚠️  PySpark not available or Spark not configured: {e}")
        print("   This test requires PySpark and Spark installed.")
        print("   You can skip this test if only using FastAPI backend.")
        return None  # Not a failure, just not applicable

    except Exception as e:
        print(f"❌ Spark UDF test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("EAOS MODEL + SPARK UDF TEST SUITE")
    print("=" * 70 + "\n")

    results = {}

    # Test 1: Model loading
    results['model_loading'] = test_model_loading()

    # Test 2: Inference
    if results['model_loading']:
        results['inference'] = test_inference()
    else:
        print("\n⚠️  Skipping inference test (model loading failed)")
        results['inference'] = False

    # Test 3: Spark UDF
    if results['model_loading']:
        results['spark_udf'] = test_spark_udf()
    else:
        print("\n⚠️  Skipping Spark UDF test (model loading failed)")
        results['spark_udf'] = False

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, result in results.items():
        status = "✅ PASS" if result else ("⚠️  SKIP" if result is None else "❌ FAIL")
        print(f"{test_name:20s}: {status}")

    print("=" * 70 + "\n")

    # Exit code
    if results['model_loading'] and results['inference']:
        print("✅ Core functionality working!")
        if results.get('spark_udf') is False:
            print("⚠️  Spark UDF test failed - check Spark configuration")
        return 0
    else:
        print("❌ Critical tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
