# Hệ thống TV Analytics - Phân tích Multi-EAOS Sentiment

Hệ thống phân tích tự động comments về chương trình TV, trích xuất EAOS (Entity-Aspect-Opinion-Sentiment) bằng mô hình PhoBERT + Transformer với điều phối bởi Apache Airflow.

## 📋 Giới thiệu

Hệ thống xử lý hàng loạt (batch processing) các comments về chương trình truyền hình, sử dụng mô hình Multi-EAOS để tự động trích xuất:

- **Entity (Thực thể)**: Chương trình, diễn viên, MC, nhân vật, địa điểm
- **Aspect (Khía cạnh)**: Nội dung, diễn xuất, dàn cast, kịch bản, âm nhạc, hình ảnh
- **Opinion (Ý kiến)**: Từ hoặc cụm từ thể hiện quan điểm của người viết
- **Sentiment (Cảm xúc)**: Tích cực, Tiêu cực, Trung tính

**Ví dụ:**
```
Input: "Chương trình rất hay, MC dẫn chương trình tốt"

Output:
[
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
]
```

## 🎯 Tính năng chính

### 1. Thu thập dữ liệu đa nguồn
- ✅ Kafka Stream (real-time streaming)
- ✅ REST API (manual submission)
- ✅ WebSocket (live comments)

### 2. Xử lý batch tự động
- ✅ Apache Airflow orchestration
- ✅ Chạy định kỳ mỗi 1 phút
- ✅ Xử lý 5 comments/batch (~300 comments/giờ)
- ✅ Retry mechanism khi lỗi

### 3. Machine Learning
- ✅ PhoBERT encoder (vinai/phobert-base)
- ✅ Custom Transformer decoder (6 layers)
- ✅ Direct inference (stable, fast)
- ✅ Confidence threshold filtering

### 4. Lưu trữ & Truy vấn
- ✅ MongoDB (central database)
- ✅ Labeled/Unlabeled comments tracking
- ✅ Real-time analytics

### 5. Visualization
- ✅ React dashboard
- ✅ Comment stream với EAOS tags
- ✅ Sentiment distribution charts
- ✅ Entity/Aspect statistics

## 🏗️ Kiến trúc

### Luồng dữ liệu chính

```
1. Data Input
   ↓
   Kafka/API/WebSocket
   ↓
2. MongoDB Storage (unlabeled)
   ↓
3. Airflow Scheduler (every 1 min)
   ↓
4. Fetch 5 unlabeled comments
   ↓
5. PySpark Service - Direct Inference
   ↓
6. Save predictions to MongoDB
   ↓
7. Frontend polls labeled comments
   ↓
8. Display EAOS visualization
```

### Components

#### Backend Services
- **FastAPI (Port 8000)**: REST API endpoints
- **PySpark Service (Port 5001)**: ML inference service
- **MongoDB (Port 27017)**: Data storage
- **Kafka (Port 9092)**: Message queue
- **Airflow (Port 8080)**: Workflow orchestration

#### Frontend
- **React App (Port 5173)**: User interface
- **WebSocket Client**: Real-time updates

#### Infrastructure
- **Docker Compose**: Multi-container orchestration
- **PostgreSQL (Port 5432)**: Airflow metadata
- **Redis (Optional)**: Caching layer

## 🚀 Hướng dẫn cài đặt

### Bước 1: Cài đặt Docker Desktop
Download và cài đặt từ: https://www.docker.com/products/docker-desktop

### Bước 2: Clone repository
```bash
git clone <repository-url>
cd FinalProject/application
```

### Bước 3: Chuẩn bị model weights
Tải model PhoBERT đã fine-tune và đặt vào:
```
application/models/checkpoints/
├── config.json
├── pytorch_model.bin
├── vocab.txt
└── training_args.bin (optional)
```

### Bước 4: Khởi động services
```bash
docker-compose up -d
```

Đợi ~2-3 phút để các services khởi động hoàn tất.

### Bước 5: Kiểm tra services đang chạy
```bash
docker ps
```

Bạn sẽ thấy các containers:
- `tv-analytics-mongodb`
- `tv-analytics-kafka`
- `tv-analytics-airflow-scheduler`
- `tv-analytics-airflow-webserver`
- `tv-analytics-pyspark`
- `tv-analytics-postgres`

### Bước 6: Truy cập Airflow UI
1. Mở browser: http://localhost:8080
2. Login: `admin` / `admin`
3. Enable DAG `batch_prediction`

### Bước 7: Khởi động Frontend (optional)
```bash
cd frontend
npm install
npm run dev
```

Truy cập: http://localhost:5173

## 💡 Cách sử dụng

### 1. Submit comments để xử lý

**Cách 1: Qua API**
```bash
curl -X POST http://localhost:8000/api/submit \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Phim hay lắm, diễn viên đóng rất tốt, nội dung hấp dẫn"
  }'
```

**Cách 2: Qua Frontend**
- Vào http://localhost:5173
- Nhập comment vào form
- Click Submit

**Cách 3: Import batch từ file**
```bash
# Tạo file test_comments.json
python add_test_comments.py
```

### 2. Theo dõi xử lý

**Airflow UI:**
1. Mở http://localhost:8080
2. Click vào DAG `batch_prediction`
3. Xem Graph View để theo dõi tiến trình
4. Click vào task để xem logs chi tiết

**MongoDB:**
```bash
# Đếm unlabeled comments
docker exec tv-analytics-mongodb mongosh \
  "mongodb://admin:admin123@localhost:27017/tv_analytics?authSource=admin" \
  --quiet --eval "db.comments.countDocuments({labels: []})"

# Đếm labeled comments
docker exec tv-analytics-mongodb mongosh \
  "mongodb://admin:admin123@localhost:27017/tv_analytics?authSource=admin" \
  --quiet --eval "db.comments.countDocuments({labels: {\$ne: []}})"
```

### 3. Xem kết quả

**API Endpoint:**
```bash
# Lấy 10 comments đã được label
curl "http://localhost:8000/api/comments/labeled?limit=10" | python -m json.tool

# Xem analytics summary
curl "http://localhost:8000/api/analytics/summary" | python -m json.tool
```

**Frontend Dashboard:**
- Mở http://localhost:5173
- Tab "Comments": Xem stream comments đã được label
- Tab "Analytics": Xem biểu đồ phân bổ sentiment
- Hover vào EAOS tags để xem chi tiết

## ⚙️ Cấu hình nâng cao

### Điều chỉnh tốc độ xử lý

**Tăng batch size (nhanh hơn):**
```python
# File: airflow/dags/batch_prediction_dag.py
# Line 76
).limit(8))  # Tăng từ 5 lên 8
```

**Tăng tần suất chạy:**
```python
# File: airflow/dags/batch_prediction_dag.py
# Line 39
schedule_interval='*/30 * * * *'  # 30 giây thay vì 1 phút
```

**Throughput ước tính:**
- Batch 5, mỗi 1 phút = 300 comments/giờ
- Batch 8, mỗi 1 phút = 480 comments/giờ
- Batch 5, mỗi 30 giây = 600 comments/giờ

### Điều chỉnh confidence threshold

```python
# File: backend/ml/eaos_model.py
inference = create_inference(
    MODEL_DIR,
    confidence_threshold=0.5  # Tăng từ 0.3 lên 0.5 để chỉ lấy predictions chắc chắn hơn
)
```

### Cấu hình MongoDB

```yaml
# File: docker-compose.yml
mongodb:
  environment:
    - MONGO_INITDB_ROOT_USERNAME=admin
    - MONGO_INITDB_ROOT_PASSWORD=admin123  # Đổi password
```

## 📊 Hiệu suất

### Metrics hiện tại
- **Batch size**: 5 comments
- **Frequency**: 1 phút
- **Method**: Direct inference
- **Throughput**: ~300 comments/giờ
- **Latency**: 2-3 giây/batch
- **Accuracy**: ~85-90% (tùy domain)

### Yêu cầu hệ thống
- **RAM**: Tối thiểu 8GB (recommend 16GB)
- **CPU**: 4 cores
- **Disk**: 20GB (cho Docker images + data)
- **GPU**: Không bắt buộc (CPU inference)

### Optimization tips
1. **Dùng GPU**: Uncomment GPU configs trong docker-compose.yml
2. **Tăng Spark memory**: Sửa `spark.driver.memory` trong spark_service.py
3. **Enable caching**: Uncomment Redis service
4. **Horizontal scaling**: Chạy nhiều Airflow workers

## 🔍 Debugging & Troubleshooting

### DAG không chạy

**Kiểm tra scheduler:**
```bash
docker logs tv-analytics-airflow-scheduler --tail 100
```

**Trigger manually:**
```bash
docker exec tv-analytics-airflow-scheduler \
  airflow dags trigger batch_prediction
```

**Check DAG file syntax:**
```bash
docker exec tv-analytics-airflow-scheduler \
  python /opt/airflow/dags/batch_prediction_dag.py
```

### PySpark Service lỗi HTTP 500

**Xem logs:**
```bash
docker logs tv-analytics-pyspark --tail 50
```

**Restart service:**
```bash
docker restart tv-analytics-pyspark
```

**Test health:**
```bash
curl http://localhost:5001/health
```

### MongoDB connection failed

**Kiểm tra MongoDB running:**
```bash
docker ps | grep mongodb
```

**Test connection:**
```bash
docker exec tv-analytics-mongodb \
  mongosh "mongodb://admin:admin123@localhost:27017/?authSource=admin" \
  --quiet --eval "db.adminCommand({ping: 1})"
```

### Frontend không hiển thị data

**Kiểm tra API:**
```bash
curl http://localhost:8000/api/comments/labeled
```

**Kiểm tra CORS:**
```python
# File: backend/api/main.py
# Thêm domain vào allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    ...
)
```

## 📁 Cấu trúc Project

```
FinalProject/
├── README.md                    # Tài liệu (English)
├── README.vi.md                 # Tài liệu (Tiếng Việt)
│
└── application/
    │
    ├── backend/
    │   ├── api/
    │   │   ├── main.py          # FastAPI app
    │   │   ├── routes.py        # API endpoints
    │   │   └── websocket.py     # WebSocket handlers
    │   │
    │   ├── ml/
    │   │   ├── eaos_model.py    # Multi-EAOS model
    │   │   └── spark_service.py # PySpark HTTP service
    │   │
    │   ├── services/
    │   │   └── comment_stream.py
    │   │
    │   └── requirements.txt
    │
    ├── frontend/
    │   ├── src/
    │   │   ├── components/      # React components
    │   │   │   ├── CommentStream.tsx
    │   │   │   ├── EAOSAnalytics.tsx
    │   │   │   └── SentimentChart.tsx
    │   │   │
    │   │   ├── services/
    │   │   │   └── api.ts       # API client
    │   │   │
    │   │   ├── types/
    │   │   │   └── index.ts     # TypeScript types
    │   │   │
    │   │   └── App.tsx
    │   │
    │   ├── package.json
    │   └── vite.config.ts
    │
    ├── airflow/
    │   ├── dags/
    │   │   ├── batch_prediction_dag.py
    │   │   └── threshold_prediction_dag.py
    │   │
    │   └── logs/                # Task execution logs
    │
    ├── models/
    │   └── checkpoints/         # Model weights
    │       ├── config.json
    │       ├── pytorch_model.bin
    │       └── vocab.txt
    │
    ├── docker-compose.yml       # Multi-service orchestration
    ├── add_test_comments.py     # Script thêm test data
    └── debug_airflow_dag.py     # Debug utilities
```

## 🔐 Security Checklist

### Development
- ✅ Default passwords (OK cho dev)
- ✅ No authentication (OK cho local)
- ✅ CORS open (OK cho localhost)

### Production Deployment
- ⚠️ **BẮT BUỘC đổi passwords**:
  ```yaml
  # MongoDB
  MONGO_INITDB_ROOT_PASSWORD: <strong-password>

  # Airflow
  _AIRFLOW_WWW_USER_PASSWORD: <strong-password>

  # PostgreSQL
  POSTGRES_PASSWORD: <strong-password>
  ```

- ⚠️ **Enable authentication**:
  - API: JWT tokens
  - Airflow: LDAP/OAuth
  - MongoDB: User roles

- ⚠️ **Network security**:
  - Reverse proxy (nginx)
  - SSL/TLS certificates
  - Firewall rules
  - VPN access

- ⚠️ **Data protection**:
  - Encrypt sensitive data
  - Backup strategy
  - Access logging

## 🧪 Testing

### Unit Tests
```bash
cd backend
pytest tests/
```

### Integration Tests
```bash
python verify_pyspark_flow.py
python test_airflow_to_pyspark.py
```

### Load Testing
```bash
# Submit 100 test comments
python add_test_comments.py --count 100
```

## 📈 Monitoring

### Airflow Metrics
- DAG success rate
- Task duration
- Failure rate
- Retry count

### System Metrics
```bash
# Docker container stats
docker stats

# MongoDB stats
docker exec tv-analytics-mongodb \
  mongosh --eval "db.serverStatus()"
```

### Application Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker logs tv-analytics-pyspark -f
```

## 🤝 Đóng góp

1. Fork repository
2. Tạo branch: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m 'Thêm tính năng X'`
4. Push: `git push origin feature/ten-tinh-nang`
5. Tạo Pull Request

## 📝 License

MIT License - Xem file LICENSE để biết thêm chi tiết

## 👥 Tác giả

- **Team SE363** - Đại học Công nghệ Thông tin (UIT)
- **Môn học**: Phân tích và Thiết kế Hệ thống
- **Project**: TV Analytics Multi-EAOS System

## 📧 Liên hệ

Mọi thắc mắc hoặc đóng góp xin liên hệ qua:
- Email: [team email]
- GitHub Issues: [repository issues]

---

**Lưu ý**: Hệ thống được phát triển cho mục đích học tập và nghiên cứu. Khi triển khai production, cần bổ sung thêm các biện pháp bảo mật và tối ưu hóa hiệu suất.

## 🎓 Tài liệu tham khảo

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [PySpark Documentation](https://spark.apache.org/docs/latest/api/python/)
- [PhoBERT Paper](https://arxiv.org/abs/2003.00744)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
