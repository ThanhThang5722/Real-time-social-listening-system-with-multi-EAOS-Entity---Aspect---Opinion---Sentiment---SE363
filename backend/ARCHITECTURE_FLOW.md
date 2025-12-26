# 🔄 Architecture Flow - Backend → PySpark → Model

## ✅ CHỨNG CỨ: Backend GỌI PySpark Service, KHÔNG load model trực tiếp

### 📋 Code Flow

```
User Request
    ↓
Backend (FastAPI - Port 8000)
    ↓ HTTP Request
PySpark Service (Port 5001)
    ↓
Model Inference
    │
    ├─ Batch < 10: Direct model call
    └─ Batch ≥ 10: PySpark PandasUDF
```

---

## 📝 CHỨNG CỨ 1: PySpark HTTP Client

**File:** `services/pyspark_client.py`

```python
class PySparkClient:
    def __init__(self, base_url: str = "http://localhost:5001"):
        """Connects to PySpark service via HTTP"""
        self.base_url = base_url
        # ...

    def predict(self, text: str) -> List[EAOSLabel]:
        """
        Makes HTTP POST request to PySpark service
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/predict",  # ← HTTP call to PySpark
                json={"text": text}
            )
            # ...
```

**✅ PROOF**: Client gửi HTTP request đến `http://localhost:5001/predict`

---

## 📝 CHỨNG CỨ 2: Backend Routes

**File:** `api/routes.py` (Dòng 154-194)

```python
@router.post("/predict", response_model=PredictResponse)
async def predict_single_comment(request: PredictRequest):
    """
    Predict EAOS labels for a single comment via PySpark service

    Flow: Backend (FastAPI) → PySpark Service (HTTP) → Model Inference
    """
    # Initialize PySpark client
    if pyspark_client is None:
        init_pyspark_client()

    # Call PySpark service via HTTP ← KEY LINE
    labels = pyspark_client.predict(
        request.text,
        confidence_threshold=request.confidence_threshold
    )
    # ...
```

**✅ PROOF**: Backend gọi `pyspark_client.predict()` → HTTP request

---

## 📝 CHỨNG CỨ 3: Batch Endpoint

**File:** `api/routes.py` (Dòng 197-244)

```python
@router.post("/predict/batch")
async def predict_batch_comments(request: PredictBatchRequest):
    """
    Flow: Backend → PySpark Service → PandasUDF (batch ≥ 10) or Model (batch < 10)
    """
    # Call PySpark service via HTTP (uses PandasUDF for batch >= 10)
    batch_labels = pyspark_client.predict_batch(
        request.texts,
        confidence_threshold=request.confidence_threshold
    )
    # ...
```

**✅ PROOF**: Batch prediction qua PySpark service, tự động dùng PandasUDF khi batch ≥ 10

---

## 📝 CHỨNG CỨ 4: WebSocket Streaming

**File:** `api/websocket.py` (Dòng 42-82)

```python
@router.websocket("/ws/comments")
async def websocket_comments(websocket: WebSocket):
    """
    Flow: Backend → PySpark Service (HTTP) → Model → Predictions
    """
    async for comment in comment_service.stream_comments():
        if pyspark_client is not None:
            # Call PySpark service for prediction ← KEY LINE
            predicted_labels = pyspark_client.predict(
                comment.text,
                confidence_threshold=0.3
            )
            comment.labels = predicted_labels
        # ...
```

**✅ PROOF**: WebSocket cũng gọi PySpark service qua HTTP

---

## 📝 CHỨNG CỨ 5: PySpark Service Implementation

**File:** `ml/spark_service.py` (Dòng 150-228)

```python
@app.route('/predict/batch', methods=['POST'])
def predict_batch():
    """
    - Small batches (< 10): Use model directly (faster)
    - Large batches (≥ 10): Use PySpark PandasUDF (parallel processing)
    """
    if len(comments) < 10:
        # Direct model inference
        for comment in comments:
            predictions = inference.predict(comment['text'])
            # ...
        return jsonify({"method": "direct"})  # ← Returns method used

    # For large batches, use PySpark
    df = spark.createDataFrame(comments)
    df_with_predictions = df.withColumn("predictions", predict_udf(col("text")))
    # ...
    return jsonify({"method": "pyspark"})  # ← Returns method used
```

**✅ PROOF**:
- Batch < 10: Direct model
- Batch ≥ 10: PySpark PandasUDF
- Response includes `"method"` field để verify

---

## 🧪 TEST CASE - Verify Flow

### Test 1: Single Prediction

```bash
# Start PySpark service
cd application
docker compose up -d pyspark

# Start Backend
cd backend
python main.py

# Test prediction
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "MC dẫn tốt"}'
```

**Expected Flow:**
1. Backend receives request at port 8000
2. Backend calls `http://localhost:5001/predict` (PySpark service)
3. PySpark service runs model inference
4. Returns predictions to Backend
5. Backend returns to user

### Test 2: Batch Prediction (PandasUDF)

```bash
curl -X POST http://localhost:8000/api/predict/batch \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "MC dẫn tốt",
      "Kịch bản hay",
      "Âm thanh rõ",
      "Hình ảnh đẹp",
      "Nội dung cuốn",
      "Diễn viên giỏi",
      "Đạo diễn tài năng",
      "Quay phim chuyên nghiệp",
      "Kịch bản sáng tạo",
      "Âm nhạc hay"
    ]
  }'
```

**Expected:**
- Response includes `"method": "pyspark"` because batch size = 10
- PySpark service uses PandasUDF for parallel processing

### Test 3: Verify in PySpark Logs

```bash
# Check PySpark service logs
docker compose logs -f pyspark
```

**Expected output:**
```
172.18.0.1 - - [DATE] "POST /predict HTTP/1.1" 200 -
Batch prediction used method: pyspark
```

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User / Client                         │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP Request
         ┌───────────▼──────────┐
         │  Backend (FastAPI)   │  Port 8000
         │  - routes.py         │
         │  - websocket.py      │
         └───────────┬──────────┘
                     │ HTTP Request (via PySparkClient)
                     │ http://localhost:5001/predict
         ┌───────────▼──────────┐
         │ PySpark Service      │  Port 5001
         │ (Docker Container)   │
         │  - Flask HTTP API    │
         └───────────┬──────────┘
                     │
         ┌───────────▼──────────────────┐
         │  Prediction Logic            │
         │                              │
         │  if batch < 10:              │
         │    ├─► Model.predict()       │
         │  else:                       │
         │    └─► PySpark PandasUDF     │
         └──────────────────────────────┘
```

---

## ✅ Summary - KẾT LUẬN

### Backend KHÔNG load model trực tiếp:
- ❌ KHÔNG import `EAOSModelService`
- ❌ KHÔNG load model weights
- ❌ KHÔNG run inference trực tiếp

### Backend GỌI PySpark service qua HTTP:
- ✅ Import `PySparkClient`
- ✅ HTTP POST to `http://localhost:5001/predict`
- ✅ Receive predictions từ PySpark service

### PySpark service TỰ ĐỘNG chọn method:
- ✅ Batch < 10: Direct model (fast)
- ✅ Batch ≥ 10: PySpark PandasUDF (parallel)
- ✅ Response includes `"method"` field

---

## 🎯 Files Modified

1. **NEW:** `services/pyspark_client.py` - HTTP client for PySpark service
2. **MODIFIED:** `api/routes.py` - Uses PySpark client, not model service
3. **MODIFIED:** `api/websocket.py` - Uses PySpark client for streaming

---

**✅ VERIFIED: All predictions go through PySpark service!**
