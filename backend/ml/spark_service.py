"""
PySpark HTTP Service - Flask API wrapper for PySpark inference

Provides HTTP endpoints for EAOS model predictions using PySpark
"""

import os
import sys
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd

# PySpark imports
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, col
from pyspark.sql.types import StringType, StructType, StructField
import pyspark.sql.functions as F

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.eaos_model import create_inference

# ============================================================================
# Initialize Flask App
# ============================================================================

app = Flask(__name__)
CORS(app)

# ============================================================================
# Global Variables
# ============================================================================

spark = None
inference = None
MODEL_DIR = os.getenv("MODEL_DIR", "./models/checkpoints")

# ============================================================================
# Initialize PySpark
# ============================================================================

def initialize_spark():
    """Initialize Spark session (local mode)"""
    global spark

    print("🚀 Initializing PySpark (local mode)...")

    spark = SparkSession.builder \
        .appName("EAOS-Service") \
        .master("local[*]") \
        .config("spark.driver.memory", "2g") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .config("spark.driver.host", "localhost") \
        .config("spark.driver.bindAddress", "localhost") \
        .config("spark.ui.enabled", "false") \
        .getOrCreate()

    print("✅ PySpark initialized")
    return spark

def initialize_model():
    """Initialize EAOS model"""
    global inference

    print(f"🤖 Loading EAOS model from {MODEL_DIR}...")

    try:
        inference = create_inference(MODEL_DIR, confidence_threshold=0.3)
        print("✅ Model loaded successfully")
        return inference
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        raise

# ============================================================================
# PandasUDF for Batch Inference
# ============================================================================

@pandas_udf(StringType())
def predict_udf(texts: pd.Series) -> pd.Series:
    """
    PandasUDF for batch prediction

    Args:
        texts: Series of comment texts

    Returns:
        Series of JSON strings containing predictions
    """
    results = []

    for text in texts:
        try:
            predictions = inference.predict(text)
            results.append(json.dumps(predictions, ensure_ascii=False))
        except Exception as e:
            results.append(json.dumps({"error": str(e)}, ensure_ascii=False))

    return pd.Series(results)

# ============================================================================
# HTTP Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "spark": spark is not None,
        "model": inference is not None
    })

@app.route('/predict', methods=['POST'])
def predict_single():
    """
    Predict single comment

    Request body:
        {
            "text": "Chương trình rất hay!"
        }

    Response:
        {
            "text": "Chương trình rất hay!",
            "predictions": [...]
        }
    """
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' field"}), 400

        text = data['text']

        # Use model directly (faster for single prediction)
        predictions = inference.predict(text)

        return jsonify({
            "text": text,
            "predictions": predictions
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/predict/batch', methods=['POST'])
def predict_batch():
    """
    Predict batch of comments

    - Small batches (< 10): Use model directly (faster)
    - Large batches (>= 10): Use PySpark PandasUDF (parallel processing)

    Request body:
        {
            "comments": [
                {"id": "1", "text": "Comment 1"},
                {"id": "2", "text": "Comment 2"}
            ]
        }

    Response:
        {
            "results": [
                {"id": "1", "text": "Comment 1", "predictions": [...]},
                {"id": "2", "text": "Comment 2", "predictions": [...]}
            ]
        }
    """
    try:
        data = request.get_json()

        if not data or 'comments' not in data:
            return jsonify({"error": "Missing 'comments' field"}), 400

        comments = data['comments']

        if not isinstance(comments, list) or len(comments) == 0:
            return jsonify({"error": "'comments' must be a non-empty list"}), 400

        # For small batches, use model directly (faster than Spark overhead)
        if len(comments) < 10:
            output = []
            for comment in comments:
                predictions = inference.predict(comment['text'])
                output.append({
                    "id": comment['id'],
                    "text": comment['text'],
                    "predictions": predictions
                })

            return jsonify({
                "results": output,
                "count": len(output),
                "method": "direct"
            })

        # For large batches, use PySpark (parallel processing)
        # Create Spark DataFrame
        df = spark.createDataFrame(comments)

        # Apply PandasUDF for batch prediction
        df_with_predictions = df.withColumn("predictions", predict_udf(col("text")))

        # Collect results
        results = df_with_predictions.select("id", "text", "predictions").collect()

        # Convert to JSON
        output = []
        for row in results:
            output.append({
                "id": row.id,
                "text": row.text,
                "predictions": json.loads(row.predictions)
            })

        return jsonify({
            "results": output,
            "count": len(output),
            "method": "pyspark"
        })

    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"❌ ERROR in /predict/batch: {error_msg}")
        print(f"Traceback:\n{error_trace}")
        return jsonify({"error": error_msg, "traceback": error_trace}), 500

@app.route('/predict/file', methods=['POST'])
def predict_file():
    """
    Predict from uploaded JSON file

    Request body:
        {
            "file_path": "./data/comments.json"
        }

    Response:
        {
            "results": [...],
            "count": 100
        }
    """
    try:
        data = request.get_json()

        if not data or 'file_path' not in data:
            return jsonify({"error": "Missing 'file_path' field"}), 400

        file_path = data['file_path']

        if not os.path.exists(file_path):
            return jsonify({"error": f"File not found: {file_path}"}), 404

        # Read JSON file with Spark
        df = spark.read.json(file_path)

        # Apply PandasUDF
        df_with_predictions = df.withColumn("predictions", predict_udf(col("text")))

        # Collect results (limit to avoid memory issues)
        limit = data.get('limit', 1000)
        results = df_with_predictions.limit(limit).select("id", "text", "predictions").collect()

        # Convert to JSON
        output = []
        for row in results:
            output.append({
                "id": row.id,
                "text": row.text,
                "predictions": json.loads(row.predictions)
            })

        return jsonify({
            "results": output,
            "count": len(output)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("PySpark EAOS Service")
    print("=" * 60)

    # Initialize Spark and Model
    initialize_spark()
    initialize_model()

    print("\n" + "=" * 60)
    print("🌐 Starting Flask server on http://0.0.0.0:5001")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /health              - Health check")
    print("  POST /predict             - Single prediction")
    print("  POST /predict/batch       - Batch prediction")
    print("  POST /predict/file        - File prediction")
    print("\n" + "=" * 60)

    # Start Flask server
    app.run(host='0.0.0.0', port=5001, debug=False)
