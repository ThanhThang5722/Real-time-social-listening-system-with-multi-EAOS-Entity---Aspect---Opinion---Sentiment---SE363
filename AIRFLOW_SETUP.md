# 🚀 Apache Airflow Setup - Pipeline Orchestration

## 📋 Tổng quan

Airflow quản lý và tự động hóa các pipeline:
- ✅ **Model Retraining**: Train lại model trên Spark (weekly)
- ✅ **Batch Prediction**: Predict batch comments (daily)
- ✅ **Scheduling**: Tự động chạy theo lịch
- ✅ **Retry**: Tự động retry khi failed
- ✅ **Logging**: Log chi tiết mọi bước
- ✅ **Monitoring**: Web UI để theo dõi

---

## 🏗️ Architecture với Airflow

```
┌─────────────────────────────────────────────────────────────┐
│                  Airflow Web UI (Port 8080)                  │
│            admin / admin - Manage & Monitor DAGs            │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼────────┐      ┌──────▼──────┐
    │  Webserver  │      │  Scheduler  │
    │  (UI/API)   │      │  (Executor) │
    └─────────────┘      └──────┬──────┘
                                │
                         ┌──────▼──────────────────┐
                         │   PostgreSQL            │
                         │   (Metadata DB)         │
                         └─────────────────────────┘

DAGs (Workflows):

1. model_retraining (Weekly - Sunday 2 AM)
   ├─► Extract data from MongoDB
   ├─► Check data quality
   ├─► Prepare training data
   ├─► Train model on Spark ← KEY TASK
   ├─► Evaluate model
   ├─► Deploy if better
   └─► Notify completion

2. batch_prediction (Daily - 3 AM)
   ├─► Fetch unlabeled comments from MongoDB
   ├─► Call PySpark service (/predict/batch)
   ├─► Save predictions to MongoDB
   ├─► Generate analytics report
   └─► Cleanup

Flow: Airflow → PySpark Service → Spark → Model → Results
```

---

## 🚀 Quick Start

### 1. Build Airflow Services

```bash
cd application

# Build Airflow image
docker compose build airflow-webserver airflow-scheduler airflow-init

# Start all services including Airflow
docker compose up -d
```

### 2. Access Airflow Web UI

Open browser: **http://localhost:8080**

**Login:**
- Username: `admin`
- Password: `admin`

### 3. Verify DAGs

You should see 2 DAGs:
1. `model_retraining` - Train model on Spark
2. `batch_prediction` - Batch predictions

---

## 📝 DAG 1: Model Retraining

**File:** `airflow/dags/model_retraining_dag.py`

**Schedule:** Every Sunday at 2 AM

**Tasks:**
```
extract_data → check_quality → prepare_data → train_model → evaluate → deploy → notify
```

### Task Details:

#### 1. Extract Data
- Pulls comments with labels from MongoDB
- Saves to `/opt/Stage2/training_data.json`

#### 2. Check Quality
- Validates minimum 100 samples
- Checks label distribution

#### 3. Prepare Data
- Converts to training format
- Splits 80/10/10 (train/val/test)

#### 4. **Train Model on Spark** ← MAIN TASK
- Runs training script: `/opt/Stage2/train_model.py`
- Uses Spark for distributed training
- Saves checkpoint to `/opt/Stage2/latest_checkpoint.pth`

#### 5. Evaluate
- Calculates validation loss
- Generates metrics (F1, precision, recall)

#### 6. Deploy if Better
- Compares new_val_loss vs current_val_loss
- If better: Deploy to `/opt/backend/models/checkpoints/`
- If not: Skip deployment

#### 7. Notify
- Sends completion notification
- Reports deployment status

### Manual Trigger:

```bash
# Via Airflow CLI in container
docker exec -it tv-analytics-airflow-scheduler \
    airflow dags trigger model_retraining

# Or click "Trigger DAG" button in Web UI
```

---

## 📝 DAG 2: Batch Prediction

**File:** `airflow/dags/batch_prediction_dag.py`

**Schedule:** Daily at 3 AM

**Tasks:**
```
fetch_comments → predict_batch → save_predictions → generate_report → cleanup
```

### Task Details:

#### 1. Fetch Comments
- Queries MongoDB for unlabeled comments
- Limit: 1000 per run

#### 2. Predict Batch
- Sends to PySpark service: `http://pyspark:5001/predict/batch`
- Auto uses PandasUDF if batch >= 10

#### 3. Save Predictions
- Updates MongoDB documents with predictions
- Adds `predicted_at` timestamp

#### 4. Generate Report
- Sentiment distribution
- Top entities
- Top aspects

#### 5. Cleanup
- Removes temporary files

### Manual Trigger:

```bash
# Via Airflow CLI
docker exec -it tv-analytics-airflow-scheduler \
    airflow dags trigger batch_prediction

# Or use Web UI
```

---

## 🔧 Configuration

### Environment Variables

Set in `docker-compose.yml`:

```yaml
environment:
  # PySpark service URL
  - PYSPARK_SERVICE_URL=http://pyspark:5001

  # Backend URL
  - BACKEND_URL=http://host.docker.internal:8000

  # Airflow database
  - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow
```

### Change Schedule

Edit DAG file:

```python
# model_retraining_dag.py
dag = DAG(
    'model_retraining',
    schedule_interval='0 2 * * 0',  # ← Change here (Cron format)
    # ...
)
```

**Cron Examples:**
- `0 2 * * 0` - Every Sunday at 2 AM
- `0 3 * * *` - Every day at 3 AM
- `0 */6 * * *` - Every 6 hours
- `@daily` - Daily at midnight
- `@weekly` - Weekly on Sunday at midnight
- `None` - Manual trigger only

---

## 📊 Monitoring & Logs

### View DAG Runs

1. Open Airflow UI: http://localhost:8080
2. Click on DAG name
3. See run history, success/failure

### View Task Logs

1. Click on task in DAG graph
2. Click "Log" button
3. See detailed execution logs

### Via Command Line

```bash
# List DAG runs
docker exec -it tv-analytics-airflow-scheduler \
    airflow dags list-runs -d model_retraining

# View task logs
docker exec -it tv-analytics-airflow-scheduler \
    airflow tasks logs model_retraining train_model 2025-01-01
```

---

## 🐛 Troubleshooting

### Issue: DAGs not appearing

**Check:**
```bash
# List all DAGs
docker exec -it tv-analytics-airflow-scheduler airflow dags list

# Check for import errors
docker exec -it tv-analytics-airflow-scheduler airflow dags list-import-errors
```

**Fix:**
- Verify DAG files in `airflow/dags/`
- Check Python syntax errors
- Restart scheduler: `docker compose restart airflow-scheduler`

### Issue: Task failed

**Check logs:**
```bash
docker compose logs airflow-scheduler
```

**Retry task:**
- Click "Clear" button in Airflow UI
- Task will retry automatically

### Issue: Cannot connect to PySpark service

**Verify:**
```bash
# Test from Airflow container
docker exec -it tv-analytics-airflow-scheduler \
    curl http://pyspark:5001/health
```

**Expected:**
```json
{"model": true, "spark": true, "status": "healthy"}
```

---

## 📁 Directory Structure

```
application/
├── airflow/
│   ├── Dockerfile              # Airflow image
│   ├── requirements.txt        # Python deps
│   ├── dags/
│   │   ├── model_retraining_dag.py     # Train DAG
│   │   └── batch_prediction_dag.py     # Prediction DAG
│   ├── logs/                   # Task logs
│   └── plugins/                # Custom plugins
│
├── docker-compose.yml          # Airflow services added
│
└── Stage2/
    ├── train_model.py          # Training script (to be created)
    ├── training_data.json      # Extracted data
    ├── train_data.json         # Training set
    ├── val_data.json           # Validation set
    └── latest_checkpoint.pth   # Trained model
```

---

## 🔄 Complete Training Pipeline Flow

```
1. Scheduled (Sunday 2 AM) or Manual Trigger
   ↓
2. Airflow Scheduler picks up DAG
   ↓
3. Extract Data Task
   MongoDB → training_data.json
   ↓
4. Prepare Data Task
   Split → train/val/test sets
   ↓
5. Train Model Task
   python /opt/Stage2/train_model.py
   ├─► Load train_data.json
   ├─► Initialize model (PhoBERT + Transformer)
   ├─► Spark distributed training
   ├─► Save checkpoint
   └─► Save training_results.json
   ↓
6. Evaluate Task
   ├─► Load checkpoint
   ├─► Test on val set
   └─► Calculate metrics
   ↓
7. Deploy Task
   if new_val_loss < current_val_loss:
       ├─► Backup current model
       ├─► Copy new model → /opt/backend/models/checkpoints/
       └─► Update config.json
   else:
       └─► Skip deployment
   ↓
8. Notify Task
   └─► Log completion status
```

---

## ✅ Checklist

Before running in production:

- [ ] Airflow services started successfully
- [ ] Can access Airflow UI (http://localhost:8080)
- [ ] Both DAGs appear in UI
- [ ] PySpark service is running (http://localhost:5001)
- [ ] MongoDB is accessible
- [ ] Training script created: `Stage2/train_model.py`
- [ ] Test DAG manually first
- [ ] Check logs for errors
- [ ] Verify model deployment works

---

## 🎯 Next Steps

### 1. Create Training Script

Create `Stage2/train_model.py` with actual training logic:

```python
# Example structure
import torch
from transformers import AutoTokenizer, AutoModel
# ... import your model

def main():
    # Load data
    with open('train_data.json') as f:
        train_data = json.load(f)

    # Initialize model
    model = MultiEAOSModel(...)

    # Training loop
    for epoch in range(num_epochs):
        # Train on Spark
        # ...

    # Save checkpoint
    torch.save({
        'model_state_dict': model.state_dict(),
        'epoch': epoch,
        'val_loss': val_loss
    }, 'latest_checkpoint.pth')

if __name__ == '__main__':
    main()
```

### 2. Test Model Retraining

```bash
# Trigger manually
docker exec -it tv-analytics-airflow-scheduler \
    airflow dags trigger model_retraining

# Watch progress in UI
# http://localhost:8080
```

### 3. Monitor Logs

```bash
# Follow scheduler logs
docker compose logs -f airflow-scheduler

# Check specific task
docker exec -it tv-analytics-airflow-scheduler \
    airflow tasks logs model_retraining train_model <run_id>
```

---

## 📚 Resources

- **Airflow Docs**: https://airflow.apache.org/docs/
- **Cron Expression**: https://crontab.guru/
- **DAG Best Practices**: https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html

---

**🎉 Airflow Setup Complete!**

Giờ bạn có thể:
- ✅ Schedule model retraining tự động
- ✅ Trigger training manually khi cần
- ✅ Monitor pipeline execution
- ✅ View detailed logs
- ✅ Retry failed tasks
- ✅ Deploy models automatically
