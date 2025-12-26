# 🚀 PySpark EAOS - Quick Start (Simple như Colab)

## Setup đơn giản - Chỉ cần Python + PySpark!

Không cần Spark cluster phức tạp, chạy local mode như trong Google Colab.

---

## ⚡ Quick Start (3 bước)

### 1. Build Docker Image
```bash
cd application
docker-compose build pyspark
```

### 2. Start Container
```bash
docker-compose up -d pyspark
```

### 3. Run Job
**Windows:**
```powershell
cd backend
.\run_spark_job.ps1
```

**Linux/Mac:**
```bash
cd backend
./run_spark_job.sh
```

---

## 📊 What's Running?

```
┌─────────────────────────────────┐
│  Python Container               │
│  - Python 3.11                  │
│  - Java 17 (for PySpark)        │
│  - PySpark (local mode)         │
│  - PyTorch + Transformers       │
│  - EAOS Model                   │
│                                 │
│  Mode: local[*]                 │
│  (Uses all CPU cores)           │
└─────────────────────────────────┘
```

**No cluster needed!** PySpark runs in local mode on single machine.

---

## 🎯 Access Points

- **Spark UI**: http://localhost:4040 (when job runs)
- **Container**: `docker exec -it tv-analytics-pyspark bash`

---

## 💻 Usage

### Example 1: Sample Data
```bash
./run_spark_job.sh
```

### Example 2: Your Data
```bash
./run_spark_job.sh \
  --input ./data/comments.json \
  --output ./results/predictions.json \
  --mode file
```

### Example 3: Interactive Python
```bash
docker exec -it tv-analytics-pyspark python
>>> from ml.eaos_model import create_inference
>>> inf = create_inference('./models/checkpoints')
>>> inf.predict("Chương trình rất hay!")
```

---

## 🔍 Verify Setup

```bash
# 1. Check container running
docker ps | grep pyspark

# 2. Check PySpark works
docker exec -it tv-analytics-pyspark python -c "from pyspark.sql import SparkSession; print('✅ PySpark OK')"

# 3. Check model exists
docker exec -it tv-analytics-pyspark ls -lh models/checkpoints/

# 4. Run test
cd backend && ./run_spark_job.sh
```

---

## 📈 Performance

**Local Mode (1 machine):**
- 10K comments: ~2-3 minutes
- 100K comments: ~10-15 minutes
- 1M comments: ~30-60 minutes

**Want faster?** Scale horizontally:
- Deploy to cloud (AWS, GCP)
- Use managed Spark (EMR, Dataproc)
- Add more machines

---

## 🐛 Troubleshooting

### "Container not running"
```bash
docker-compose up -d pyspark
docker ps | grep pyspark
```

### "Model not found"
```bash
# Copy checkpoint
cp Stage2/latest_checkpoint.pth backend/models/checkpoints/
cp Stage2/config.json backend/models/checkpoints/
```

### "Out of memory"
Edit docker-compose.yml:
```yaml
environment:
  - SPARK_DRIVER_MEMORY=8g  # Increase if needed
```

---

## ✅ Advantages vs Cluster Setup

| Feature | Simple (This) | Cluster |
|---------|--------------|---------|
| Setup Time | 5 minutes | 30+ minutes |
| Complexity | Low | High |
| Resources | Lightweight | Heavy |
| Perfect for | < 10M rows | > 10M rows |
| Works on | Any OS | Linux best |

---

## 🎓 How It Works

```python
# spark_inference.py uses local mode:
spark = SparkSession.builder \
    .master("local[*]") \  # ← Local mode, all cores
    .getOrCreate()

# Same PandasUDF code
@pandas_udf(StringType())
def eaos_predict_udf(texts):
    # Batch prediction
    # Fast on single machine!
```

---

## 📚 Next Steps

1. ✅ Test with sample data
2. ✅ Process your real dataset
3. ✅ Monitor via Spark UI (http://localhost:4040)
4. ✅ Scale to cloud if needed

---

**🎉 Simple, fast, effective!**

Like Colab, but in Docker 🐳
