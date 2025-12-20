# Quick Start Guide

## Chạy nhanh trong 3 bước

### 1. Chạy Backend (Terminal 1)

```bash
cd application/backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python main.py
```

✅ Backend sẽ chạy tại `http://localhost:8000`

### 2. Chạy Frontend (Terminal 2)

```bash
cd application/frontend
npm install
npm run dev
```

✅ Frontend sẽ chạy tại `http://localhost:3000`

### 3. Truy cập Dashboard

Mở browser: `http://localhost:3000`

## Các tính năng chính

1. **Comment Stream** (Tab đầu tiên)
   - Xem bình luận real-time
   - Mỗi comment có EAOS labels (Entity, Aspect, Opinion, Sentiment)

2. **Analytics** (Tab thứ hai)
   - Thống kê tổng số comments, entities, aspects
   - Biểu đồ phân bố sentiment
   - Top entities và aspects

3. **Chat Assistant** (Tab thứ ba)
   - Hỏi: "Tổng quan bình luận"
   - Hỏi: "Phân tích cảm xúc"
   - Hỏi: "Có vấn đề gì không?"

## Kiểm tra hoạt động

1. Backend API: `http://localhost:8000/docs`
2. Health check: `http://localhost:8000/`
3. Analytics: `http://localhost:8000/api/analytics/summary`

## Troubleshooting

**Backend không chạy?**
- Kiểm tra Python 3.8+ đã cài đặt: `python --version`
- Thử cài lại dependencies: `pip install -r requirements.txt`

**Frontend không chạy?**
- Kiểm tra Node.js 18+ đã cài đặt: `node --version`
- Xóa và cài lại: `rm -rf node_modules && npm install`

**WebSocket không kết nối?**
- Đảm bảo backend đang chạy
- Kiểm tra firewall/antivirus không block port 8000

## Next Steps

- Xem [README.md](README.md) để biết chi tiết về architecture
- Tích hợp Kafka cho production streaming
- Thay thế mock EAOS analyzer bằng ML model thực
