# TV Analytics System - Multi-EAOS Sentiment Analysis

Hệ thống phân tích sentiment và trích xuất EAOS (Entity-Aspect-Opinion-Sentiment) từ comments về chương trình TV sử dụng PhoBERT + Transformer với Apache Airflow orchestration.

## 📋 Tổng quan

Hệ thống xử lý batch comments về chương trình TV, sử dụng mô hình Multi-EAOS để trích xuất:
- **Entity** (Thực thể): Chương trình, diễn viên, MC, nhân vật
- **Aspect** (Khía cạnh): Nội dung, diễn xuất, dàn cast, kịch bản, v.v.
- **Opinion** (Ý kiến): Từ/cụm từ thể hiện quan điểm
- **Sentiment** (Cảm xúc): Tích cực, Tiêu cực, Trung tính

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
│  • Kafka Stream (real-time comments)                            │
│  • API Submit (manual comments)                                 │
│  • WebSocket (live comments)                                    │
└────────────────────┬────────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MongoDB (Central Database)                    │
│  Collection: comments                                            │
│  • Unlabeled comments (labels: [])                              │
│  • Labeled comments (labels: [{entity, aspect, opinion, ...}])  │
└────────────────────┬────────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Apache Airflow (Workflow Orchestration)             │
│                                                                  │
│  DAG: batch_prediction (runs every 1 minute)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. fetch_comments → MongoDB (5 unlabeled/batch)          │  │
│  │ 2. predict_batch → PySpark Service (HTTP POST)           │  │
│  │ 3. save_predictions → MongoDB (update labels)            │  │
│  │ 4. generate_report → Analytics                           │  │
│  │ 5. cleanup → Temp files                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PySpark Service (Flask API)                     │
│                                                                  │
│  Port: 5001                                                     │
│  Method: Direct Inference (batch < 10)                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Multi-EAOS Model (PhoBERT + Transformer)                │   │
│  │ • Encoder: vinai/phobert-base                           │   │
│  │ • Decoder: Custom Transformer (6 layers)                │   │
│  │ • Output: EAOS quadruples with confidence               │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Backend API (FastAPI)                           │
│  Port: 8000                                                     │
│  • POST /api/submit - Submit new comments                       │
│  • GET /api/comments/labeled - Get labeled comments             │
│  • GET /api/analytics/summary - Get analytics                   │
│  • WebSocket /ws/comments - Live stream                         │
└────────────────────┬────────────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                       │
│  Port: 5173                                                     │
│  • Comment Stream (labeled comments only)                       │
│  • Analytics Dashboard (sentiment distribution)                │
│  • EAOS Visualization                                           │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 Tech Stack

### Backend & ML
- **Python 3.11**
- **FastAPI** - REST API framework
- **PySpark 3.5** - Distributed processing
- **PyTorch** - Deep learning framework
- **Transformers (Hugging Face)** - PhoBERT model
- **MongoDB** - NoSQL database
- **Apache Kafka** - Message streaming
- **Apache Airflow** - Workflow orchestration

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **D3.js** - Data visualization
- **Recharts** - Charts

### DevOps
- **Docker & Docker Compose** - Containerization
- **PostgreSQL** - Airflow metadata
- **Redis** (optional) - Caching

## 📦 Cài đặt

### Prerequisites
- Docker Desktop
- Python 3.11+
- Node.js 18+

### 1. Clone repository
```bash
git clone <repository-url>
cd FinalProject
```

### 2. Chuẩn bị model checkpoints
Đặt model weights vào thư mục:
```
application/models/checkpoints/
├── config.json
├── pytorch_model.bin
└── vocab.txt
```

### 3. Khởi động services với Docker Compose
```bash
cd application
docker-compose up -d
```

Services sẽ chạy trên:
- **MongoDB**: localhost:27017
- **Kafka**: localhost:9092
- **Airflow UI**: localhost:8080 (admin/admin)
- **PySpark Service**: localhost:5001
- **Backend API**: localhost:8000
- **Frontend**: localhost:5173
- **PostgreSQL** (Airflow): localhost:5432

### 4. Khởi động Frontend (development)
```bash
cd application/frontend
npm install
npm run dev
```

## 🚀 Sử dụng

### 1. Submit comments
**Qua API:**
```bash
curl -X POST http://localhost:8000/api/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Chương trình rất hay, MC dẫn chương trình tốt"}'
```

**Response:**
```json
{
  "status": "submitted",
  "comment_id": "...",
  "message": "Comment saved. Will be processed in next batch (every 1 min)."
}
```

### 2. Theo dõi processing
- Mở Airflow UI: http://localhost:8080
- Login: admin/admin
- Xem DAG `batch_prediction`
- Theo dõi task execution

### 3. Xem kết quả

**Qua API:**
```bash
curl http://localhost:8000/api/comments/labeled?limit=10
```

**Response:**
```json
{
  "total": 14,
  "comments": [
    {
      "_id": "...",
      "text": "Chương trình rất hay, MC dẫn chương trình tốt",
      "labels": [
        {
          "entity": "Chương trình",
          "aspect": "Nội dung",
          "opinion": "rất hay",
          "sentiment": "tích cực",
          "confidence": 0.95
        },
        {
          "entity": "MC",
          "aspect": "Dẫn chương trình",
          "opinion": "tốt",
          "sentiment": "tích cực",
          "confidence": 0.92
        }
      ],
      "predicted_at": "2025-12-27T09:29:00Z"
    }
  ]
}
```

**Qua Frontend:**
- Mở http://localhost:5173
- Xem comment stream với EAOS labels
- Xem analytics dashboard

## ⚙️ Cấu hình

### Airflow DAG Settings
File: `application/airflow/dags/batch_prediction_dag.py`

```python
# Tần suất chạy
schedule_interval='*/1 * * * *'  # Mỗi 1 phút

# Batch size
.limit(5)  # 5 comments/batch

# Throughput: ~300 comments/hour
```

### PySpark Service Settings
File: `application/backend/ml/spark_service.py`

```python
# Memory allocation
.config("spark.driver.memory", "2g")

# Inference method threshold
if len(comments) < 10:
    # Use direct inference (faster, stable)
else:
    # Use PySpark PandasUDF (parallel, for large batches)
```

### Model Settings
```python
# Confidence threshold
confidence_threshold = 0.3  # Chỉ lấy predictions có confidence > 0.3
```

## 📊 Performance

### Current Configuration
- **Batch size**: 5 comments
- **Frequency**: Every 1 minute
- **Method**: Direct inference
- **Throughput**: ~300 comments/hour
- **Latency**: ~2-3 seconds/batch

### Scaling Options
1. **Tăng batch size** → 8-9 comments (vẫn dùng direct inference)
2. **Tăng frequency** → 30 seconds
3. **Parallel DAGs** → Chạy nhiều DAG instances

## 🔍 Monitoring

### Airflow UI
- DAG runs history
- Task logs
- Execution timeline
- Retry/failure tracking

### MongoDB
```bash
# Count unlabeled
db.comments.countDocuments({labels: []})

# Count labeled
db.comments.countDocuments({labels: {$ne: []}})

# Sample EAOS
db.comments.findOne({labels: {$ne: []}})
```

### PySpark Service Health
```bash
curl http://localhost:5001/health
```

Response:
```json
{
  "status": "healthy",
  "model": true,
  "spark": true
}
```

## 🐛 Troubleshooting

### Airflow DAG không chạy
```bash
# Check scheduler logs
docker logs tv-analytics-airflow-scheduler

# Manually trigger DAG
docker exec tv-analytics-airflow-scheduler \
  airflow dags trigger batch_prediction
```

### PySpark Service lỗi
```bash
# Check logs
docker logs tv-analytics-pyspark

# Restart service
docker restart tv-analytics-pyspark
```

### MongoDB connection issues
```bash
# Test connection
docker exec tv-analytics-mongodb \
  mongosh "mongodb://admin:admin123@localhost:27017/?authSource=admin"
```

## 📁 Cấu trúc thư mục

```
FinalProject/
├── application/
│   ├── backend/
│   │   ├── api/              # FastAPI routes
│   │   ├── ml/               # ML models & PySpark service
│   │   │   ├── eaos_model.py
│   │   │   └── spark_service.py
│   │   └── services/         # Business logic
│   │
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── components/   # React components
│   │   │   ├── services/     # API clients
│   │   │   └── types/        # TypeScript types
│   │   └── vite.config.ts
│   │
│   ├── airflow/
│   │   └── dags/
│   │       ├── batch_prediction_dag.py
│   │       └── threshold_prediction_dag.py
│   │
│   ├── models/
│   │   └── checkpoints/      # Model weights
│   │
│   └── docker-compose.yml    # Multi-service orchestration
│
└── README.md
```

## 🔐 Security Notes

### Production Deployment
1. **Đổi passwords mặc định**:
   - MongoDB: admin/admin123
   - Airflow: admin/admin
   - PostgreSQL: airflow/airflow

2. **Enable authentication**:
   - API authentication (JWT)
   - CORS configuration
   - Rate limiting

3. **Network security**:
   - Reverse proxy (nginx)
   - SSL/TLS certificates
   - Firewall rules

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -m 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit Pull Request

## 📝 License

[MIT License](LICENSE)

## 👥 Authors

- **Team SE363** - UIT
- **Project**: TV Analytics Multi-EAOS System

## 📧 Contact

For questions or support, please contact the development team.

---

**Note**: This system is designed for educational and research purposes. For production deployment, additional security hardening and performance optimization are recommended.
