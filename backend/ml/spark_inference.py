"""
Spark + PandasUDF for Distributed EAOS Inference

Usage:
    # Run standalone
    python -m ml.spark_inference --model-dir ./models/best_model

    # Or import
    from ml.spark_inference import run_spark_job
    run_spark_job(model_dir="./models/best_model", mode="console")
"""

import sys
import json
import pandas as pd
import torch
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, PandasUDFType, col
from pyspark.sql.types import StringType, StructType, StructField, ArrayType

# Import model
from .eaos_model import load_model, EAOSInference


# ============================================================================
# GLOBAL MODEL (loaded once per executor)
# ============================================================================

_model = None
_tokenizer = None
_config = None
_inference = None


def initialize_model(model_dir: str):
    """Initialize model on Spark executor (called once per worker)"""
    global _model, _tokenizer, _config, _inference

    if _model is None:
        print(f"[Spark Executor] Loading model from: {model_dir}")

        # Load model on CPU for Spark workers
        device = torch.device('cpu')
        _model, _tokenizer, _config = load_model(model_dir, device=device)
        _inference = EAOSInference(_model, _tokenizer, _config, confidence_threshold=0.5)

        print(f"[Spark Executor] Model loaded successfully")

    return _inference


# ============================================================================
# PANDAS UDF for VECTORIZED INFERENCE
# ============================================================================

def create_eaos_udf(model_dir: str):
    """
    Create PandasUDF for EAOS inference

    This UDF processes BATCHES of rows (vectorized) instead of one-by-one
    Result: 10-100x faster than standard UDF!
    """

    @pandas_udf(StringType(), PandasUDFType.SCALAR)
    def eaos_predict_udf(texts: pd.Series) -> pd.Series:
        """
        Predict EAOS labels for batch of texts

        Args:
            texts: Pandas Series of input texts

        Returns:
            Pandas Series of JSON predictions
        """
        # Initialize model (once per executor)
        inference = initialize_model(model_dir)

        # Batch inference
        results = []
        for text in texts:
            try:
                predictions = inference.predict(text)
                results.append(json.dumps(predictions, ensure_ascii=False))
            except Exception as e:
                print(f"[UDF Error] {e}")
                results.append("[]")

        return pd.Series(results)

    return eaos_predict_udf


# ============================================================================
# SPARK JOB
# ============================================================================

def run_spark_job(
    model_dir: str,
    input_path: str = None,
    output_path: str = None,
    mode: str = "console"
):
    """
    Run Spark inference job

    Args:
        model_dir: Path to model directory
        input_path: Input data path (CSV/JSON/Parquet)
        output_path: Output path for results
        mode: "console" | "file" | "memory"
    """

    print("=" * 70)
    print("EAOS Spark Inference Job")
    print("=" * 70)

    # Create Spark session
    spark = SparkSession.builder \
        .appName("EAOS-Inference") \
        .master("spark://localhost:7077") \
        .config("spark.executor.memory", "4g") \
        .config("spark.driver.memory", "2g") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    print(f"✅ Spark session created")
    print(f"   Master: spark://localhost:7077")
    print(f"   App ID: {spark.sparkContext.applicationId}")

    # Create UDF
    print(f"\n🔧 Creating PandasUDF with model: {model_dir}")
    eaos_udf = create_eaos_udf(model_dir)

    # Sample data (for testing)
    if input_path is None:
        print("\n📝 Using sample data...")
        sample_data = [
            ("1", "Chương trình rất hay!"),
            ("2", "MC dẫn tốt, kịch bản cuốn"),
            ("3", "Mùa này không hay bằng mùa trước"),
            ("4", "Running Man Việt Nam rất vui"),
            ("5", "Trấn Thành dẫn chương trình xuất sắc")
        ]
        df = spark.createDataFrame(sample_data, ["id", "text"])
    else:
        print(f"\n📂 Reading data from: {input_path}")
        df = spark.read.json(input_path)

    # Apply UDF
    print("\n⚡ Running inference with PandasUDF...")
    result_df = df.withColumn("predictions", eaos_udf(col("text")))

    # Output
    if mode == "console":
        print("\n📊 Results:\n")
        result_df.show(truncate=False)

    elif mode == "file" and output_path:
        print(f"\n💾 Writing results to: {output_path}")
        result_df.write.mode("overwrite").json(output_path)
        print("✅ Done!")

    elif mode == "memory":
        # Return as Pandas DataFrame
        return result_df.toPandas()

    # Cleanup
    spark.stop()
    print("\n" + "=" * 70)
    print("✅ Job completed!")
    print("=" * 70)


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Spark EAOS Inference")
    parser.add_argument("--model-dir", required=True, help="Model directory path")
    parser.add_argument("--input", help="Input data path (optional)")
    parser.add_argument("--output", help="Output path (optional)")
    parser.add_argument("--mode", choices=["console", "file", "memory"], default="console")

    args = parser.parse_args()

    # Validate paths
    model_dir = Path(args.model_dir).resolve()
    if not model_dir.exists():
        print(f"❌ Model directory not found: {model_dir}")
        sys.exit(1)

    # Run job
    try:
        run_spark_job(
            model_dir=str(model_dir),
            input_path=args.input,
            output_path=args.output,
            mode=args.mode
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Job interrupted by user")
    except Exception as e:
        print(f"\n❌ Job failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
