# Database Migration Guide

Guide để migrate từ old schema sang new unified schema.

## 📋 Schema Changes Summary

### Redis Keys Structure

**Old:**
- `eaos:{entity}` → JSON with score and metadata
- `trend:{time_window}m` → Sorted set
- `metrics:{metric_name}` → List

**New:**
- `eaos:current:{program_id}` → Hash {score, positive, negative, neutral, total, updated_at}
- `trends:top:{time_range}` → Sorted Set {topic: score}
- `events:{program_id}:{date}` → List of events (JSON)

### ClickHouse Tables

**Old:**
- `comments` - Mixed sentiment and EAOS data
- `eaos_metrics` - Different structure

**New:**
- `eaos_metrics` - program_id, timestamp, score, positive_count, negative_count, neutral_count, total_comments
- `comment_aggregates` - program_id, timestamp, topic, count, avg_sentiment
- `anomalies` - program_id, timestamp, metric, value, expected, deviation, severity
- `raw_comments` - Detailed comment storage

### Elasticsearch Index

**Old:**
- Various fields, less structured

**New:**
- Standardized fields: text, program_id, timestamp, sentiment, engagement_score, topics[]

## 🔄 Migration Steps

### Step 1: Backup Existing Data

```bash
# Backup Redis
redis-cli --rdb dump.rdb

# Backup ClickHouse
clickhouse-client --query="CREATE TABLE tv_analytics.comments_backup AS tv_analytics.comments"

# Backup Elasticsearch
curl -X POST "localhost:9200/tv_comments/_clone/tv_comments_backup"
```

### Step 2: Stop Services

```bash
# Stop application
# Stop Docker services if needed
docker-compose down
```

### Step 3: Update ClickHouse Schema

```bash
# Connect to ClickHouse
docker exec -it tv-analytics-clickhouse clickhouse-client

# Run new schema
SOURCE /path/to/002_updated_schema.sql
```

Or from host:

```bash
cat scripts/clickhouse-init/002_updated_schema.sql | docker exec -i tv-analytics-clickhouse clickhouse-client --database=tv_analytics
```

### Step 4: Clear Old Redis Data

```bash
# Connect to Redis
docker exec -it tv-analytics-redis redis-cli

# Clear old keys (CAREFUL!)
FLUSHDB

# Or selectively delete
KEYS eaos:*
DEL ...
```

### Step 5: Update Application Code

Update imports to use V2 clients:

```python
# Old
from src.storage.redis_client import redis_client
from src.storage.clickhouse_client import clickhouse_client
from src.storage.elasticsearch_client import elasticsearch_client

# New
from src.storage.redis_client_v2 import redis_client_v2
from src.storage.clickhouse_client_v2 import clickhouse_client_v2
from src.storage.elasticsearch_client_v2 import elasticsearch_client_v2
```

### Step 6: Re-initialize Databases

```bash
# Start services
docker-compose up -d

# Wait for services to be ready
sleep 10

# Initialize with new schema
python scripts/init_databases.py
```

### Step 7: Seed New Data

```bash
# Seed sample data with new schema
python scripts/seed_sample_data_v2.py --count 100
```

### Step 8: Verify Migration

```bash
# Test new storage clients
python tests/test_storage_v2.py

# Test agent with new schema
python tests/test_agent.py --mode interactive
```

## 🧪 Testing New Schema

### Test Redis V2

```python
from src.storage.redis_client_v2 import redis_client_v2
import asyncio

async def test():
    await redis_client_v2.connect()

    # Test EAOS
    await redis_client_v2.set_current_eaos(
        program_id="test_show",
        score=0.85,
        positive=100,
        negative=20,
        neutral=30,
        total=150
    )

    eaos = await redis_client_v2.get_current_eaos("test_show")
    print("EAOS:", eaos)

    # Test trends
    await redis_client_v2.add_trending_topic("15min", "contestant_1", 50)
    trends = await redis_client_v2.get_top_trends("15min", limit=5)
    print("Trends:", trends)

    await redis_client_v2.disconnect()

asyncio.run(test())
```

### Test ClickHouse V2

```python
from src.storage.clickhouse_client_v2 import clickhouse_client_v2
from datetime import datetime

clickhouse_client_v2.connect()

# Insert EAOS metric
clickhouse_client_v2.insert_eaos_metric(
    program_id="test_show",
    timestamp=datetime.now(),
    score=0.85,
    positive_count=100,
    negative_count=20,
    neutral_count=30,
    total_comments=150
)

# Get latest EAOS
eaos = clickhouse_client_v2.get_latest_eaos("test_show")
print("Latest EAOS:", eaos)

clickhouse_client_v2.disconnect()
```

### Test Elasticsearch V2

```python
from src.storage.elasticsearch_client_v2 import elasticsearch_client_v2
import asyncio
from datetime import datetime

async def test():
    await elasticsearch_client_v2.connect()

    # Index comment
    await elasticsearch_client_v2.index_comment(
        comment_id="test_001",
        program_id="test_show",
        text="Great show!",
        username="viewer123",
        timestamp=datetime.now(),
        sentiment="positive",
        sentiment_score=0.9,
        engagement_score=50,
        topics=["show", "performance"]
    )

    # Search
    results = await elasticsearch_client_v2.search_comments(
        program_id="test_show",
        query="great"
    )
    print("Search results:", len(results))

    await elasticsearch_client_v2.disconnect()

asyncio.run(test())
```

## 📊 Data Mapping

### Entity → Program ID

Old schema used generic "entity" (contestant, segment).
New schema uses "program_id" for consistency.

**Mapping:**
- `contestant_1` → `program_id: "show_name/contestant_1"`
- `segment_intro` → `program_id: "show_name/segment_intro"`
- Or keep as is if program context is clear

### Time Windows

Old: `5`, `15`, `60` (integers)
New: `"5min"`, `"15min"`, `"1hour"` (strings)

**Update code:**
```python
# Old
time_window = 15

# New
time_range = "15min"
```

### Sentiment Labels

Standardized to English:
- `tích cực` → `positive`
- `tiêu cực` → `negative`
- `trung lập` → `neutral`

## 🔧 Rollback Plan

If migration fails:

### Rollback Redis

```bash
# Restore from backup
redis-cli --rdb dump.rdb
redis-cli SHUTDOWN SAVE
# Restart Redis
```

### Rollback ClickHouse

```sql
-- Restore from backup
DROP TABLE IF EXISTS tv_analytics.eaos_metrics;
RENAME TABLE tv_analytics.comments_backup TO tv_analytics.comments;
```

### Rollback Elasticsearch

```bash
# Delete new index
curl -X DELETE "localhost:9200/tv_comments"

# Restore from backup
curl -X POST "localhost:9200/tv_comments_backup/_clone/tv_comments"
```

### Rollback Code

```bash
git checkout HEAD~1  # Or specific commit
# Revert to old client imports
```

## ⚠️ Important Notes

1. **Test on staging first!** Never migrate production directly
2. **Backup everything** before starting
3. **Monitor logs** during migration
4. **Verify data integrity** after migration
5. **Update documentation** with new schema
6. **Inform team** about schema changes

## 📝 Post-Migration Checklist

- [ ] All services running
- [ ] New schema tables created
- [ ] Sample data seeded
- [ ] Storage clients working
- [ ] Agent tools functional
- [ ] API endpoints updated
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Team notified

## 🆘 Troubleshooting

### "Table already exists" error

Solution: Drop old tables first or use `CREATE TABLE IF NOT EXISTS`

### Redis connection refused

Solution: Check Docker service status, restart if needed

### Elasticsearch mapping conflict

Solution: Delete index and recreate with new mapping

### ClickHouse query timeout

Solution: Increase timeout in client config or optimize query

## 📚 References

- [Redis Data Types](https://redis.io/docs/data-types/)
- [ClickHouse Schema Design](https://clickhouse.com/docs/en/engines/table-engines/)
- [Elasticsearch Mapping](https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping.html)

---

**Migration completed successfully! 🎉**

Next: Update FastAPI endpoints to use V2 clients.
