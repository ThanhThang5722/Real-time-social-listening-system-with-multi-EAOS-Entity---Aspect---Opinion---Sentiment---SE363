# 🎯 Multi-EAOS Model Integration Guide

## Tổng quan
Backend đã được tích hợp model Multi-EAOS để tự động phát hiện Entity-Aspect-Opinion-Sentiment từ comment text.

---

## 📁 Cấu trúc files

```
application/backend/
├── models/
│   ├── checkpoints/
│   │   ├── latest_checkpoint.pth (1.7GB) - Model weights
│   │   └── config.json - Model configuration
│   ├── multi_eaos_model.py - Model architecture
│   └── schemas.py - Pydantic schemas
├── services/
│   ├── eaos_model_service.py - Model inference service
│   ├── comment_stream.py - Comment streaming (updated)
│   └── eaos_analyzer.py - Analytics service
├── api/
│   ├── routes.py - REST API endpoints
│   └── websocket.py - WebSocket endpoints
└── main.py - FastAPI application
```

---

## 🚀 Khởi động Backend

### 1. Cài đặt dependencies
```bash
cd application/backend
pip install -r requirements.txt
```

### 2. Chạy server
```bash
python main.py
```

hoặc

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server sẽ chạy tại: http://localhost:8000

---

## 📡 API Endpoints

### 1. WebSocket - Stream Comments với Predictions

**Endpoint:** `ws://localhost:8000/api/ws/comments`

**Mô tả:** Stream comments real-time với EAOS predictions tự động

**Response Example:**
```json
{
  "type": "comment",
  "data": {
    "id": "comment_123_1234567890.123",
    "text": "Chương trình rất hay và bổ ích!",
    "labels": [
      {
        "entity": "chương trình",
        "aspect": "Kịch bản",
        "opinion": "rất hay",
        "sentiment": "tích cực"
      }
    ],
    "timestamp": "2025-12-26T10:30:00",
    "username": "user123"
  }
}
```

### 2. POST /api/predict - Single Comment Prediction

**Endpoint:** `POST http://localhost:8000/api/predict`

**Request Body:**
```json
{
  "text": "Mùa này không hay bằng mùa trước",
  "confidence_threshold": 0.3
}
```

**Response:**
```json
{
  "text": "Mùa này không hay bằng mùa trước",
  "labels": [
    {
      "entity": "mùa này",
      "aspect": "Kịch bản",
      "opinion": "không hay",
      "sentiment": "tiêu cực"
    }
  ],
  "count": 1
}
```

### 3. POST /api/predict/batch - Batch Prediction

**Endpoint:** `POST http://localhost:8000/api/predict/batch`

**Request Body:**
```json
{
  "texts": [
    "Chương trình rất hay!",
    "Âm thanh hơi nhỏ",
    "Diễn viên diễn xuất tốt"
  ],
  "confidence_threshold": 0.3
}
```

**Response:**
```json
{
  "total": 3,
  "results": [
    {
      "text": "Chương trình rất hay!",
      "labels": [...],
      "count": 1
    },
    {
      "text": "Âm thanh hơi nhỏ",
      "labels": [...],
      "count": 1
    },
    {
      "text": "Diễn viên diễn xuất tốt",
      "labels": [...],
      "count": 1
    }
  ]
}
```

---

## ⚙️ Cấu hình Model

### Thay đổi Confidence Threshold
- **Mặc định:** 0.3
- **Điều chỉnh:** Thay đổi giá trị trong request body
- **Ý nghĩa:** Ngưỡng tin cậy tối thiểu để chấp nhận prediction (0.0 - 1.0)

### Model Configuration (config.json)
```json
{
  "model_name": "vinai/phobert-base",
  "num_aspects": 11,
  "num_sentiments": 3,
  "max_len": 256,
  "max_quads": 4,
  "best_epoch": 110,
  "best_val_loss": 14.70
}
```

### Aspect Categories (11 loại)
1. Địa điểm
2. Kịch bản
3. Dàn dựng
4. Dàn cast
5. Khách mời
6. Khả năng chơi trò chơi
7. Quảng cáo
8. Thử thách
9. Tương tác giữa các thành viên
10. Tinh thần đồng đội
11. Khác

### Sentiment Categories (3 loại)
- Tích cực (1)
- Tiêu cực (2)
- Trung tính (0)

---

## 🧪 Test API

### Sử dụng curl
```bash
# Test single prediction
curl -X POST "http://localhost:8000/api/predict" \
  -H "Content-Type: application/json" \
  -d '{"text": "Chương trình rất hay!", "confidence_threshold": 0.3}'

# Test batch prediction
curl -X POST "http://localhost:8000/api/predict/batch" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Text 1", "Text 2"], "confidence_threshold": 0.3}'
```

### Sử dụng Python
```python
import requests

# Single prediction
response = requests.post(
    "http://localhost:8000/api/predict",
    json={
        "text": "Chương trình rất hay!",
        "confidence_threshold": 0.3
    }
)
print(response.json())

# Batch prediction
response = requests.post(
    "http://localhost:8000/api/predict/batch",
    json={
        "texts": ["Text 1", "Text 2"],
        "confidence_threshold": 0.3
    }
)
print(response.json())
```

### Sử dụng WebSocket (JavaScript)
```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/comments');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received comment:', data);
};

ws.onopen = () => {
  console.log('Connected to comment stream');
};
```

---

## 🔧 Troubleshooting

### Lỗi: Model không load được
```
⚠️  Warning: Failed to load EAOS model
```

**Giải pháp:**
1. Kiểm tra file checkpoint tồn tại: `models/checkpoints/latest_checkpoint.pth`
2. Kiểm tra file config tồn tại: `models/checkpoints/config.json`
3. Kiểm tra đã cài đặt: `torch`, `transformers`, `sentencepiece`

### Lỗi: Out of Memory (CUDA)
**Giải pháp:**
- Model sẽ tự động chuyển sang CPU nếu không có GPU
- Giảm batch size nếu dùng batch prediction

### Lỗi: Prediction chậm
**Giải pháp:**
- Sử dụng GPU nếu có (tự động detect)
- Giảm max_len trong config (hiện tại: 256)
- Tăng confidence_threshold để lọc kết quả nhanh hơn

---

## 📊 Performance

- **Model size:** 1.7GB (checkpoint)
- **Inference time (CPU):** ~0.5-1s per comment
- **Inference time (GPU):** ~0.1-0.2s per comment
- **Max quadruples per comment:** 4
- **Supported text length:** Up to 256 tokens

---

## 🎓 Model Information

- **Base Model:** PhoBERT (vinai/phobert-base)
- **Architecture:** BERT + Transformer + Multi-Head Attention
- **Training Epochs:** 110 (best model)
- **Validation Loss:** 14.70
- **Training Data:** 2,049 samples
- **Validation Data:** 513 samples

---

## 📝 Notes

1. **Model tự động load khi start server**
   - Nếu load thất bại, server vẫn chạy nhưng không có predictions

2. **Comments từ stream chỉ chứa text**
   - Labels được predict real-time bởi model

3. **Confidence threshold**
   - Mặc định: 0.3
   - Giá trị thấp hơn → nhiều predictions hơn (có thể sai)
   - Giá trị cao hơn → ít predictions hơn (chính xác hơn)

4. **GPU vs CPU**
   - Model tự động phát hiện và sử dụng GPU nếu có
   - CPU vẫn hoạt động nhưng chậm hơn

---

## 🆘 Support

Nếu gặp vấn đề, kiểm tra:
1. Server logs khi khởi động
2. API docs tại: http://localhost:8000/docs
3. Health check: http://localhost:8000/
