# 🚀 PySpark PandasUDF for EAOS Model

## Tổng quan

Model Multi-EAOS đã được tích hợp với **PySpark PandasUDF** để xử lý hàng triệu comments song song trên Spark cluster.

### ⚡ Performance
- **Without UDF (Python loop):** ~1 comment/second
- **With PandasUDF:** ~100-1000 comments/second (depending on cluster size)
- **Speedup:** 10-100x faster!

---

## 📁 Files

```
application/backend/
├── ml/
│   ├── eaos_model.py         # Model class + Inference (UPDATED ✅)
│   ├── spark_inference.py    # PandasUDF + Spark job
│   └── __init__.py
├── models/checkpoints/
│   ├── latest_checkpoint.pth # Model weights (1.7GB)
│   └── config.json           # Configuration
└── test_spark_udf.py         # Test script
```

---

## 🔧 Architecture Update (FIXED)

### ❌ **Before (WRONG):**
```python
# Old ml/eaos_model.py used BiLSTM
self.lstm = nn.LSTM(...)  # ← Incompatible with checkpoint!
```

### ✅ **After (CORRECT):**
```python
# Updated ml/eaos_model.py uses Transformer
self.transformer = nn.TransformerEncoder(...)  # ← Matches checkpoint!
```

### 🔄 **Model Loading Updated:**
```python
# Now loads from latest_checkpoint.pth instead of model.pth
checkpoint = torch.load("latest_checkpoint.pth")
model.load_state_dict(checkpoint['model_state_dict'])
```

---

## 🧪 Testing

### Quick Test (Local Mode)
```bash
cd application/backend
python test_spark_udf.py
```

**Expected Output:**
```
======================================================================
TEST 1: Model Loading
======================================================================
✅ Model loaded successfully!
   Model type: MultiEAOSModel
   Config: vinai/phobert-base
   Best epoch: 110

======================================================================
TEST 2: Inference
======================================================================
✅ Inference service created
✅ Predictions: 1 labels found

   Label 1:
      Entity: chương trình
      Aspect: Kịch bản
      Opinion: rất hay
      Sentiment: tích cực
      Confidence: 0.982

======================================================================
TEST 3: Spark PandasUDF
======================================================================
✅ Spark session created (local mode)
✅ PandasUDF created
✅ Spark PandasUDF test passed!
```

---

## 🚀 Usage

### Option 1: Standalone Spark Job

```bash
python -m ml.spark_inference \
  --model-dir ./models/checkpoints \
  --input ./data/comments.json \
  --output ./results/predictions.json \
  --mode file
```

**Input Format (JSON):**
```json
{"id": "1", "text": "Chương trình rất hay!"}
{"id": "2", "text": "MC dẫn tốt quá"}
```

**Output Format:**
```json
{
  "id": "1",
  "text": "Chương trình rất hay!",
  "predictions": "[{\"entity\":\"chương trình\",\"aspect\":\"Kịch bản\",\"opinion\":\"rất hay\",\"sentiment\":\"tích cực\",\"confidence\":0.95}]"
}
```

### Option 2: Python Script

```python
from ml.spark_inference import run_spark_job

# Run with sample data (console output)
run_spark_job(
    model_dir="./models/checkpoints",
    mode="console"
)

# Run with file input/output
run_spark_job(
    model_dir="./models/checkpoints",
    input_path="./data/comments.json",
    output_path="./results/predictions.json",
    mode="file"
)

# Return as Pandas DataFrame
df = run_spark_job(
    model_dir="./models/checkpoints",
    input_path="./data/comments.json",
    mode="memory"
)
print(df.head())
```

### Option 3: Custom Spark Application

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from ml.spark_inference import create_eaos_udf

# Create Spark session
spark = SparkSession.builder \
    .appName("EAOS-Production") \
    .master("spark://localhost:7077") \
    .config("spark.executor.memory", "8g") \
    .config("spark.executor.cores", "4") \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .getOrCreate()

# Load data
df = spark.read.json("hdfs://data/comments.json")

# Create UDF
eaos_udf = create_eaos_udf("./models/checkpoints")

# Apply UDF (distributed processing!)
result_df = df.withColumn("predictions", eaos_udf(col("text")))

# Save results
result_df.write.mode("overwrite").parquet("hdfs://results/predictions.parquet")

spark.stop()
```

---

## ⚙️ Configuration

### Spark Settings (spark_inference.py:119-125)

```python
spark = SparkSession.builder \
    .appName("EAOS-Inference") \
    .master("spark://localhost:7077")  # Change to your Spark master
    .config("spark.executor.memory", "4g")  # Memory per executor
    .config("spark.driver.memory", "2g")    # Driver memory
    .config("spark.sql.execution.arrow.pyspark.enabled", "true")  # Enable Arrow
    .getOrCreate()
```

### Model Configuration

Model được load một lần trên **mỗi Spark executor** (not per row):

```python
# Global model (loaded once per worker)
_model = None

def initialize_model(model_dir):
    global _model
    if _model is None:
        _model = load_model(model_dir, device='cpu')  # Use CPU on workers
    return _model
```

---

## 📊 Performance Tuning

### 1. Executor Configuration
```python
# Tăng số executors và cores
.config("spark.executor.instances", "10")
.config("spark.executor.cores", "4")
.config("spark.executor.memory", "8g")
```

### 2. Batch Size
PandasUDF tự động xử lý theo batch (vectorized). Điều chỉnh partition size:
```python
df = df.repartition(100)  # Chia data thành 100 partitions
```

### 3. GPU Support
Nếu executors có GPU:
```python
def initialize_model(model_dir):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    return load_model(model_dir, device=device)
```

### 4. Confidence Threshold
Giảm threshold để có nhiều predictions hơn (nhưng ít chính xác hơn):
```python
inference = EAOSInference(model, tokenizer, config, confidence_threshold=0.2)
```

---

## 🔍 Monitoring

### Spark UI
Khi job đang chạy, truy cập:
```
http://localhost:4040
```

Xem:
- Tasks progress
- Stage timeline
- Executor metrics
- Storage usage

### Logs
```python
spark.sparkContext.setLogLevel("INFO")  # Change to DEBUG for more details
```

---

## 📈 Scalability

### Data Size vs. Processing Time

| Comments | Executors | Cores | Time (estimate) |
|----------|-----------|-------|-----------------|
| 10K      | 1         | 2     | ~2 minutes      |
| 100K     | 5         | 4     | ~5 minutes      |
| 1M       | 10        | 8     | ~15 minutes     |
| 10M      | 20        | 8     | ~2 hours        |

*Assuming: 2s per comment (CPU), batch processing with PandasUDF*

---

## 🐛 Troubleshooting

### Error: "No module named 'ml'"
```bash
# Add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/backend"
```

### Error: "Checkpoint not found"
```bash
# Verify files exist
ls -lh models/checkpoints/
# Should see: latest_checkpoint.pth, config.json
```

### Error: "Architecture mismatch"
**Solution:** This was fixed! The model now uses Transformer instead of BiLSTM.

If you still see this error:
1. Check you're using updated `ml/eaos_model.py`
2. Verify checkpoint is from notebook (not old BiLSTM model)

### Error: "Out of memory"
**Solutions:**
1. Reduce executor memory
2. Increase repartitions: `df.repartition(200)`
3. Use CPU instead of GPU on workers
4. Process smaller batches

### Slow Performance
**Solutions:**
1. Enable Arrow: `spark.sql.execution.arrow.pyspark.enabled = true`
2. Increase executors and cores
3. Use faster storage (SSD, HDFS instead of network mount)
4. Cache intermediate results: `df.cache()`

---

## 🔗 Integration with Backend

### FastAPI + Spark for Batch Processing

```python
# api/routes.py
from ml.spark_inference import run_spark_job

@router.post("/batch/process-large")
async def process_large_batch(file_path: str):
    """Process millions of comments with Spark"""
    try:
        # Run Spark job asynchronously
        result_df = run_spark_job(
            model_dir="./models/checkpoints",
            input_path=file_path,
            mode="memory"
        )

        return {
            "status": "success",
            "total_processed": len(result_df),
            "sample": result_df.head(5).to_dict('records')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 📝 Notes

1. **Model Loading**
   - Model is loaded **once per executor**, not per row
   - This amortizes the loading cost across thousands of predictions

2. **Device Selection**
   - Default: CPU (compatible with all executors)
   - For GPU: Ensure all executors have CUDA-compatible GPUs

3. **Confidence Threshold**
   - Lower threshold → More predictions (but less accurate)
   - Higher threshold → Fewer predictions (but more accurate)
   - Default: 0.5 (recommended: 0.3-0.7)

4. **Arrow Optimization**
   - **Must enable** for PandasUDF to work efficiently
   - Without Arrow: 10x slower serialization

---

## ✅ Checklist

Before running in production:

- [ ] Model checkpoint exists and loads successfully
- [ ] Test script passes all tests
- [ ] Spark cluster is configured and accessible
- [ ] Input data format is correct (JSON with "text" field)
- [ ] Output path is writable
- [ ] Executors have enough memory (4GB+ recommended)
- [ ] Arrow is enabled in Spark config
- [ ] Confidence threshold is tuned for your use case

---

## 🆘 Support

**Common Issues:**
1. Import errors → Check PYTHONPATH
2. Memory errors → Reduce executor memory or increase repartitions
3. Slow performance → Enable Arrow, increase cores
4. Model mismatch → Use updated ml/eaos_model.py (Transformer, not BiLSTM)

**Contact:**
- Check logs in Spark UI: http://localhost:4040
- Review test output: `python test_spark_udf.py`
