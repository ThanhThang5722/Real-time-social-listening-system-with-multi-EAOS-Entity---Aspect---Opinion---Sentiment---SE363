# 🚀 PySpark HTTP Service - Quick Start

## Tổng quan

PySpark service với HTTP API - giao tiếp qua port thay vì copy dữ liệu vào container.

### ✅ Lợi ích
- **Không cần copy data vào container** - chỉ cần gửi HTTP request
- **Hoạt động trên Windows** - PySpark chạy trong Linux container
- **Dễ dùng** - REST API đơn giản
- **PandasUDF** - batch processing với PySpark

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                 Host Machine                     │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  Python Script / Client                    │ │
│  │  sends HTTP requests to port 5001          │ │
│  └──────────────────┬─────────────────────────┘ │
│                     │ HTTP (port 5001)           │
│  ┌──────────────────▼─────────────────────────┐ │
│  │  Docker Container: tv-analytics-pyspark    │ │
│  │                                            │ │
│  │  ┌────────────────────────────────────┐   │ │
│  │  │  Flask HTTP Server (port 5001)     │   │ │
│  │  └─────────────┬──────────────────────┘   │ │
│  │                │                            │ │
│  │  ┌─────────────▼──────────────────────┐   │ │
│  │  │  PySpark (local mode)              │   │ │
│  │  │  - PandasUDF for batch inference   │   │ │
│  │  │  - EAOS Model                      │   │ │
│  │  └────────────────────────────────────┘   │ │
│  │                                            │ │
│  │  Ports: 5001 (API), 4040 (Spark UI)       │ │
│  └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### 1. Build và Start Service

```bash
cd application

# Build image
docker-compose build pyspark

# Start service
docker-compose up -d pyspark

# Check logs
docker-compose logs -f pyspark
```

**Expected output:**
```
🚀 Initializing PySpark (local mode)...
✅ PySpark initialized
🤖 Loading EAOS model from ./models/checkpoints...
✅ Model loaded successfully
🌐 Starting Flask server on http://0.0.0.0:5001
```

### 2. Test Service

```bash
cd backend

# Test với Python script
python test_pyspark_service.py
```

### 3. Verify

```bash
# Health check
curl http://localhost:5001/health

# Should return:
# {
#   "status": "healthy",
#   "spark": true,
#   "model": true
# }
```

---

## 📡 HTTP API Endpoints

### 1. Health Check

**GET** `/health`

```bash
curl http://localhost:5001/health
```

**Response:**
```json
{
  "status": "healthy",
  "spark": true,
  "model": true
}
```

### 2. Single Prediction

**POST** `/predict`

```bash
curl -X POST http://localhost:5001/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Chương trình rất hay!"}'
```

**Request:**
```json
{
  "text": "Chương trình rất hay!"
}
```

**Response:**
```json
{
  "text": "Chương trình rất hay!",
  "predictions": [
    {
      "entity": "Chương trình",
      "aspect": "TÍNH NĂNG",
      "opinion": "hay",
      "sentiment": "POSITIVE",
      "confidence": 0.92
    }
  ]
}
```

### 3. Batch Prediction (PySpark PandasUDF)

**POST** `/predict/batch`

```bash
curl -X POST http://localhost:5001/predict/batch \
  -H "Content-Type: application/json" \
  -d '{
    "comments": [
      {"id": "1", "text": "Chương trình rất hay!"},
      {"id": "2", "text": "MC dẫn tốt"}
    ]
  }'
```

**Request:**
```json
{
  "comments": [
    {"id": "1", "text": "Chương trình rất hay!"},
    {"id": "2", "text": "MC dẫn tốt"}
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "1",
      "text": "Chương trình rất hay!",
      "predictions": [...]
    },
    {
      "id": "2",
      "text": "MC dẫn tốt",
      "predictions": [...]
    }
  ],
  "count": 2
}
```

### 4. File Prediction

**POST** `/predict/file`

```bash
curl -X POST http://localhost:5001/predict/file \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/app/data/comments.json", "limit": 100}'
```

**Request:**
```json
{
  "file_path": "/app/data/comments.json",
  "limit": 100
}
```

**Response:**
```json
{
  "results": [...],
  "count": 100
}
```

---

## 💻 Usage Examples

### Python Client

```python
import requests
import json

# Base URL
BASE_URL = "http://localhost:5001"

# 1. Health check
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# 2. Single prediction
response = requests.post(
    f"{BASE_URL}/predict",
    json={"text": "Chương trình rất hay!"}
)
print(response.json())

# 3. Batch prediction
response = requests.post(
    f"{BASE_URL}/predict/batch",
    json={
        "comments": [
            {"id": "1", "text": "Comment 1"},
            {"id": "2", "text": "Comment 2"}
        ]
    }
)
print(response.json())
```

### JavaScript/Node.js

```javascript
// Fetch API
fetch('http://localhost:5001/predict', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: 'Chương trình rất hay!' })
})
  .then(res => res.json())
  .then(data => console.log(data));
```

### cURL (Bash)

```bash
# Single prediction
curl -X POST http://localhost:5001/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Chương trình rất hay!"}'

# Batch prediction
curl -X POST http://localhost:5001/predict/batch \
  -H "Content-Type: application/json" \
  -d @batch_request.json
```

---

## 🔍 Monitoring

### Service Status

```bash
# Check if service is running
docker ps | grep pyspark

# View logs
docker-compose logs -f pyspark

# Health check
curl http://localhost:5001/health
```

### Spark UI

When a Spark job is running:
- Open browser: **http://localhost:4040**
- View stages, tasks, and performance metrics

### Container Shell

```bash
# Access container
docker exec -it tv-analytics-pyspark bash

# Check model files
ls -lh /app/models/checkpoints/

# Test model directly
python -c "from ml.eaos_model import create_inference; inf = create_inference('./models/checkpoints'); print(inf.predict('Test'))"
```

---

## 🐛 Troubleshooting

### Issue: "Connection refused"

**Check if service is running:**
```bash
docker ps | grep pyspark
```

**Start service:**
```bash
docker-compose up -d pyspark
```

### Issue: "Model not found"

**Verify model files exist:**
```bash
ls -lh application/backend/models/checkpoints/
# Should see: latest_checkpoint.pth, config.json
```

**Copy from Stage2 if missing:**
```bash
cp Stage2/latest_checkpoint.pth application/backend/models/checkpoints/
cp Stage2/config.json application/backend/models/checkpoints/
```

### Issue: "Service unhealthy"

**Check logs:**
```bash
docker-compose logs pyspark
```

**Restart service:**
```bash
docker-compose restart pyspark
```

### Issue: "Out of memory"

**Increase driver memory:**

Edit `ml/spark_service.py`:
```python
spark = SparkSession.builder \
    .config("spark.driver.memory", "8g") \  # Increase from 4g
    .getOrCreate()
```

Rebuild:
```bash
docker-compose build pyspark
docker-compose up -d pyspark
```

---

## 📊 Performance

### Single Prediction
- **Latency**: ~100-200ms per comment
- **Use case**: Real-time API, webhooks

### Batch Prediction (PySpark)
- **Throughput**: ~100-500 comments/second (depends on hardware)
- **Use case**: Batch processing, data pipelines

**Benchmark:**
```bash
# Test 1000 comments
python -c "
import requests
import time

start = time.time()
response = requests.post('http://localhost:5001/predict/batch', json={
    'comments': [{'id': str(i), 'text': f'Comment {i}'} for i in range(1000)]
})
elapsed = time.time() - start
print(f'Time: {elapsed:.2f}s')
print(f'Throughput: {1000/elapsed:.0f} comments/sec')
"
```

---

## 🚀 Integration Examples

### Example 1: Backend FastAPI Integration

```python
# In your FastAPI backend
import httpx

async def predict_comment(text: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5001/predict",
            json={"text": text}
        )
        return response.json()
```

### Example 2: Batch Processing Pipeline

```python
import requests
import json

def process_large_dataset(input_file, output_file):
    # Read data
    with open(input_file) as f:
        comments = [json.loads(line) for line in f]

    # Send to PySpark service
    response = requests.post(
        "http://localhost:5001/predict/batch",
        json={"comments": comments}
    )

    # Save results
    with open(output_file, 'w') as f:
        json.dump(response.json()['results'], f, ensure_ascii=False, indent=2)

process_large_dataset('input.jsonl', 'output.json')
```

---

## 🔒 Production Considerations

### Security

```yaml
# docker-compose.yml
environment:
  - API_KEY=${API_KEY}  # Add API key authentication
```

### Scaling

```bash
# Scale horizontally (multiple instances)
docker-compose up -d --scale pyspark=3
```

Add load balancer (nginx, traefik) in front.

### Monitoring

- Add Prometheus metrics
- Add health check alerts
- Add request logging

---

## ✅ Checklist

- [ ] Service starts successfully
- [ ] Health check returns `{"status": "healthy"}`
- [ ] Model loads without errors
- [ ] Single prediction works
- [ ] Batch prediction works
- [ ] Spark UI accessible (during job)
- [ ] No memory issues

---

## 📚 Next Steps

1. ✅ Test locally with sample data
2. ✅ Integrate with your backend
3. ✅ Process real dataset
4. ✅ Monitor performance
5. ✅ Scale if needed

---

**🎉 Enjoy your PySpark service!**

Simple, fast, and easy to use! 🐳
