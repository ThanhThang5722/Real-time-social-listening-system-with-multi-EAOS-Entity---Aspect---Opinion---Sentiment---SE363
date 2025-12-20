# 📺 TV Producer Analytics AI Agent

An intelligent AI agent system that helps TV producers monitor and analyze real-time audience engagement during live broadcasts using natural language queries.

## 🎯 Overview

This system combines:
- **EAOS Analytics** (Engagement-Adjusted Opinion Score) from viewer comments
- **AI Agent** with multi-step reasoning using LangGraph + Vertex AI Gemini Pro
- **Real-time Data Processing** with Redis, ClickHouse, and Elasticsearch
- **LLM Observability** via LangFuse with ClickHouse storage backend

### Key Features

- 💬 **Natural Language Interface**: Ask questions like "Why did sentiment drop at minute 25?"
- 📊 **Real-time EAOS Tracking**: Monitor audience opinion scores with sentiment breakdown
- 🔥 **Hot Trends Detection**: Track trending topics and keywords from viewer comments
- 🚨 **Anomaly Detection**: Automatically detect unusual patterns in engagement metrics
- 🤖 **Multi-step Reasoning**: Agent plans and executes complex analytical queries
- 📈 **LLM Cost Tracking**: Monitor all AI calls and costs via LangFuse dashboard

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          FastAPI REST API                        │
│              /chat  /eaos  /trends  /health                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    LangGraph AI Agent                            │
│   Workflow: understand → plan → execute → observe → synthesize  │
└───┬──────────────────────┬──────────────────────────┬───────────┘
    │                      │                          │
    ▼                      ▼                          ▼
┌─────────┐         ┌──────────────┐         ┌──────────────┐
│ Vertex  │         │  11 Agent    │         │  LangFuse    │
│ AI      │◄────────┤  Tools       │────────►│ Observability│
│ Gemini  │         │              │         │ (ClickHouse) │
└─────────┘         └──────────────┘         └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ┌────────┐        ┌─────────────┐    ┌──────────────┐
   │ Redis  │        │ ClickHouse  │    │Elasticsearch │
   │ Cache  │        │ Time-Series │    │ Full-Text    │
   │ Hot    │        │ Analytics   │    │ Search       │
   └────────┘        └─────────────┘    └──────────────┘
```

### Tech Stack

- **AI/ML**: LangChain, LangGraph, Vertex AI Gemini Pro 1.5
- **Databases**: Redis 7, ClickHouse 23.8, Elasticsearch 8.11, PostgreSQL 15
- **Backend**: FastAPI, Python 3.11, Pydantic
- **Observability**: LangFuse (self-hosted with ClickHouse backend)
- **Infrastructure**: Docker Compose

## 🚀 Quick Start (5 minutes)

### Prerequisites

- Docker and Docker Compose installed
- 8GB RAM minimum
- Ports available: 8000, 6379, 8123, 9200, 3000, 5432

### 1. Clone and Setup Environment

```bash
cd application
cp .env.example .env
```

### 2. Start All Services

```bash
docker-compose up -d
```

This starts:
- Redis (port 6379)
- ClickHouse (port 8123, 9000)
- Elasticsearch (port 9200)
- LangFuse Server (port 3000)
- PostgreSQL for LangFuse (port 5432)

Wait 30 seconds for all services to be healthy:

```bash
docker-compose ps
```

### 3. Initialize Databases

```bash
# ClickHouse tables are auto-created via init scripts
# Elasticsearch index will be created on first use

# Verify ClickHouse
curl "http://localhost:8123/?query=SHOW TABLES"
```

### 4. Configure GCP Credentials (Required for AI Agent)

You need a Google Cloud service account with Vertex AI access:

```bash
# Edit .env and update:
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
VERTEX_AI_LOCATION=us-central1
```

Place your service account JSON in the path specified.

### 5. Setup LangFuse (For Observability)

1. Open http://localhost:3000
2. Create an account (first user becomes admin)
3. Create a new project
4. Go to Settings → API Keys
5. Copy Public Key and Secret Key
6. Update `.env`:
   ```bash
   LANGFUSE_ENABLED=true
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=http://localhost:3000
   ```

### 6. Seed Sample Data

```bash
python scripts/seed_sample_data.py
```

This populates:
- Redis with current EAOS scores and trends
- ClickHouse with historical EAOS timeline data
- Elasticsearch with sample comments

### 7. Start FastAPI Application

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run FastAPI
uvicorn src.api.main:app --reload --port 8000
```

### 8. Test the Agent

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Chat with agent
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "program_id": "show_123",
    "message": "What is the current EAOS score?",
    "verbose": true
  }'
```

## 📡 API Endpoints

### 1. Chat with AI Agent

**POST** `/api/v1/chat`

Ask natural language questions about TV program analytics.

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "program_id": "show_123",
    "message": "Why did sentiment drop at minute 25?",
    "verbose": true
  }'
```

**Request:**
```json
{
  "program_id": "show_123",
  "message": "Why did sentiment drop at minute 25?",
  "verbose": true
}
```

**Response:**
```json
{
  "response": "Sentiment dropped at minute 25 because...",
  "program_id": "show_123",
  "sources": [
    {"type": "eaos_timeline", "data": {...}},
    {"type": "comments", "data": [...]}
  ],
  "reasoning_steps": [
    {"step": "understand", "output": {...}},
    {"step": "plan", "output": {...}},
    {"step": "execute", "tools_called": ["get_eaos_timeline", "search_comments"]}
  ],
  "metadata": {
    "timestamp": "2025-01-15T10:30:00Z",
    "execution_time_ms": 2341,
    "llm_calls": 3,
    "tools_executed": 2
  }
}
```

**Sample Queries:**
- "EAOS hiện tại của chương trình là bao nhiêu?"
- "Top 5 chủ đề đang hot nhất?"
- "Tại sao sentiment giảm mạnh ở phút 25?"
- "So sánh EAOS của chương trình này với tuần trước"
- "Có anomaly nào trong 30 phút qua không?"

**Rate Limit:** 60 requests/minute per IP

### 2. Get Current EAOS

**GET** `/api/v1/eaos/current/{program_id}`

Get the most recent EAOS score with sentiment breakdown.

```bash
curl http://localhost:8000/api/v1/eaos/current/show_123
```

**Response:**
```json
{
  "program_id": "show_123",
  "score": 0.78,
  "positive": 450,
  "negative": 120,
  "neutral": 230,
  "total": 800,
  "updated_at": "2025-01-15T10:30:00Z"
}
```

**Cache:** 30 seconds TTL

### 3. Get EAOS Timeline

**GET** `/api/v1/eaos/timeline/{program_id}`

Get historical EAOS scores over time.

```bash
curl "http://localhost:8000/api/v1/eaos/timeline/show_123?from_time=2025-01-15T09:00:00Z&to_time=2025-01-15T10:00:00Z&granularity=5min"
```

**Query Parameters:**
- `from_time` (optional): Start time (ISO format, default: 1 hour ago)
- `to_time` (optional): End time (ISO format, default: now)
- `granularity` (optional): minute, 5min, segment (default: 5min)

**Response:**
```json
{
  "program_id": "show_123",
  "timeline": [
    {
      "timestamp": "2025-01-15T09:00:00Z",
      "score": 0.75,
      "positive_count": 120,
      "negative_count": 30,
      "neutral_count": 50,
      "total_comments": 200
    }
  ],
  "granularity": "5min",
  "from_time": "2025-01-15T09:00:00Z",
  "to_time": "2025-01-15T10:00:00Z"
}
```

**Cache:** 60 seconds TTL

### 4. Get Trending Topics

**GET** `/api/v1/trends`

Get currently trending topics from viewer comments.

```bash
curl "http://localhost:8000/api/v1/trends?limit=10&time_range=15min"
```

**Query Parameters:**
- `limit` (optional): Number of topics (1-50, default: 10)
- `time_range` (optional): 5min, 15min, 1hour (default: 15min)

**Response:**
```json
{
  "trends": [
    {"topic": "plot_twist", "score": 234.5, "rank": 1},
    {"topic": "acting", "score": 189.2, "rank": 2},
    {"topic": "music", "score": 156.7, "rank": 3}
  ],
  "time_range": "15min",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Cache:** 60 seconds TTL

### 5. Health Check

**GET** `/api/v1/health`

Check status of all backend services.

```bash
curl http://localhost:8000/api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "services": {
    "redis": "healthy",
    "clickhouse": "healthy",
    "elasticsearch": "healthy"
  },
  "version": "1.0.0"
}
```

**Status Levels:**
- `healthy`: All services operational
- `degraded`: Some non-critical services down (Redis, Elasticsearch)
- `unhealthy`: Critical services down (ClickHouse)

## 🤖 AI Agent Architecture

### LangGraph Workflow

The agent uses a 6-node workflow with multi-step reasoning:

```
┌──────────────┐
│  understand  │  Extract intent, entities, time frame
└──────┬───────┘
       │
┌──────▼───────┐
│     plan     │  Create execution plan with tools
└──────┬───────┘
       │
┌──────▼───────┐
│   execute    │◄──┐ Execute tools from plan
└──────┬───────┘   │
       │           │
┌──────▼───────┐   │
│   observe    │   │ Evaluate: need more data?
└──────┬───────┘   │
       │           │
       ├───────────┘ (continue_execution)
       │
┌──────▼───────┐
│  synthesize  │  Combine findings into insights
└──────┬───────┘
       │
┌──────▼───────┐
│   respond    │  Generate final response
└──────────────┘
```

### 11 Agent Tools

| Tool | Description |
|------|-------------|
| `get_current_eaos` | Get current EAOS score with sentiment breakdown |
| `get_eaos_timeline` | Get EAOS timeline over time period |
| `get_trending_topics` | Get hot topics from viewer comments |
| `get_topic_details` | Get detailed analysis of specific topic |
| `search_comments` | Full-text search in comments |
| `get_sample_comments` | Get sample comments by sentiment/time |
| `analyze_comment_themes` | Extract themes using LLM |
| `detect_anomalies` | Detect statistical outliers in metrics |
| `get_program_events` | Get program events from timeline |
| `generate_recommendation` | Generate actionable recommendations |
| `get_comparative_analysis` | Compare metrics across programs/time periods |

### Example Agent Execution

**Query:** "Why did sentiment drop at minute 25?"

**Workflow:**
1. **Understand**: Intent=investigation, entity=time:25min, metric=sentiment
2. **Plan**:
   - Step 1: get_eaos_timeline (last 1 hour)
   - Step 2: get_program_events (around minute 25)
   - Step 3: search_comments (minute 25, negative sentiment)
3. **Execute**: Run tools in sequence
4. **Observe**: Check if we have enough data (yes)
5. **Synthesize**: Correlate EAOS drop with program event and comment themes
6. **Respond**: "Sentiment dropped at minute 25 because a controversial scene aired..."

## 🗄️ Database Schemas

### Redis

**Key Structures:**

```
eaos:current:{program_id}           # Hash - Current EAOS score
  ├─ score: 0.78
  ├─ positive: 450
  ├─ negative: 120
  ├─ neutral: 230
  ├─ total: 800
  └─ updated_at: 2025-01-15T10:30:00Z

trends:top:{time_range}             # Sorted Set - Trending topics
  ├─ "plot_twist" → 234.5
  ├─ "acting" → 189.2
  └─ "music" → 156.7

events:{program_id}:{date}          # List - Program events
  └─ [{timestamp, event_type, description}, ...]
```

### ClickHouse

**Tables:**

```sql
-- EAOS time-series metrics
eaos_metrics (
    program_id String,
    timestamp DateTime,
    score Float32,
    positive_count UInt32,
    negative_count UInt32,
    neutral_count UInt32,
    total_comments UInt32
)
PARTITION BY toYYYYMM(timestamp)
ORDER BY (program_id, timestamp)

-- Aggregated comments by topic
comment_aggregates (
    program_id String,
    timestamp DateTime,
    topic String,
    count UInt32,
    avg_sentiment Float32
)

-- Detected anomalies
anomalies (
    program_id String,
    timestamp DateTime,
    metric String,
    value Float32,
    expected Float32,
    deviation Float32,
    severity String  -- low, medium, high, critical
)
```

### Elasticsearch

**Index: comments**

```json
{
  "comment_id": "c123",
  "program_id": "show_123",
  "text": "Amazing plot twist!",
  "username": "user456",
  "timestamp": "2025-01-15T10:30:00Z",
  "sentiment": "positive",
  "sentiment_score": 0.85,
  "engagement_score": 42,
  "topics": ["plot", "twist"],
  "metadata": {}
}
```

## 📊 LangFuse Observability

LangFuse tracks all LLM calls and tool executions with cost/performance metrics.

### Accessing LangFuse Dashboard

1. Open http://localhost:3000
2. Login with your credentials
3. Select your project

### What's Tracked

- **Traces**: Each agent query creates a trace
- **Generations**: All Vertex AI Gemini Pro calls
- **Spans**: Tool executions with duration
- **Costs**: Token usage and estimated costs
- **Metadata**: Program IDs, session IDs, user context

### Storage Backend

LangFuse uses **dual storage**:
- **PostgreSQL**: User accounts, projects, API keys
- **ClickHouse**: Traces, observations, spans (high-performance time-series)

This hybrid approach provides:
- Fast writes to ClickHouse for high-volume trace data
- Reliable PostgreSQL for critical metadata
- Efficient querying of trace timelines

### Example Trace

```
Trace: agent_query
├─ Generation: understand (Gemini Pro) - 234ms, 456 tokens
├─ Span: tool_get_eaos_timeline - 89ms
├─ Span: tool_search_comments - 145ms
├─ Generation: synthesize (Gemini Pro) - 312ms, 678 tokens
└─ Total: 2.3s, 1134 tokens, $0.0023
```

## 🧪 Testing

### Run All Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires running services)
pytest tests/integration/

# End-to-end test
python scripts/test_e2e.py
```

### Manual Testing Script

```bash
# Test health check
curl http://localhost:8000/api/v1/health | jq

# Test EAOS endpoints
curl http://localhost:8000/api/v1/eaos/current/show_123 | jq
curl "http://localhost:8000/api/v1/eaos/timeline/show_123?granularity=5min" | jq

# Test trends
curl "http://localhost:8000/api/v1/trends?limit=5" | jq

# Test agent queries
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "program_id": "show_123",
    "message": "What is the current EAOS score?",
    "verbose": true
  }' | jq
```

## 🔧 Configuration

### Environment Variables

Key settings in `.env`:

```bash
# GCP Vertex AI
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-1.5-pro
VERTEX_AI_TEMPERATURE=0.1
VERTEX_AI_MAX_OUTPUT_TOKENS=8192

# LangFuse Observability
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000

# Cache TTL (seconds)
CACHE_TTL_EAOS_CURRENT=30
CACHE_TTL_EAOS_TIMELINE=60
CACHE_TTL_TRENDS=60

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10

# EAOS Calculation Weights
EAOS_WEIGHT_SENTIMENT=0.6
EAOS_WEIGHT_ENGAGEMENT=0.4
```

### Adjusting Performance

**For higher throughput:**
```bash
# Increase Redis maxmemory
redis: --maxmemory 2gb

# Increase ClickHouse connections
CLICKHOUSE_MAX_POOL_SIZE=20

# Lower cache TTL for fresher data
CACHE_TTL_EAOS_CURRENT=10
```

**For cost optimization:**
```bash
# Use lower temperature for cheaper calls
VERTEX_AI_TEMPERATURE=0.0

# Reduce max tokens
VERTEX_AI_MAX_OUTPUT_TOKENS=4096

# Increase cache TTL
CACHE_TTL_EAOS_CURRENT=60
```

## 🐛 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs -f clickhouse
docker-compose logs -f elasticsearch

# Check ports
netstat -an | grep 8123
netstat -an | grep 9200

# Restart services
docker-compose down
docker-compose up -d
```

### LangFuse Connection Failed

**Symptom:** "Failed to initialize LangFuse" in logs

**Solutions:**
1. Verify LangFuse is running: `docker-compose ps langfuse-server`
2. Check API keys are correct in `.env`
3. Ensure ClickHouse is healthy: `docker-compose ps clickhouse`
4. Check LangFuse logs: `docker-compose logs -f langfuse-server`

### Agent Returns Empty Responses

**Symptom:** Chat endpoint returns but response is empty

**Solutions:**
1. Check GCP credentials are valid
2. Verify Vertex AI API is enabled in GCP console
3. Check agent logs: `tail -f logs/agent.log`
4. Test Gemini Pro directly:
   ```python
   from google.cloud import aiplatform
   aiplatform.init(project="your-project", location="us-central1")
   ```

### No Data in Queries

**Symptom:** EAOS/trends endpoints return empty arrays

**Solutions:**
1. Verify seed script ran: `python scripts/seed_sample_data.py`
2. Check Redis: `redis-cli KEYS eaos:*`
3. Check ClickHouse: `curl "http://localhost:8123/?query=SELECT count() FROM eaos_metrics"`
4. Check Elasticsearch: `curl http://localhost:9200/comments/_count`

### High Response Times

**Symptom:** Chat endpoint takes >5 seconds

**Solutions:**
1. Enable caching in `.env`: `CACHE_ENABLED=true`
2. Increase cache TTL: `CACHE_TTL_EAOS_TIMELINE=300`
3. Reduce max_iterations: `AGENT_MAX_ITERATIONS=3`
4. Use faster model: `VERTEX_AI_MODEL=gemini-1.5-flash`

## 📚 Project Structure

```
application/
├── docker-compose.yml           # All services (Redis, ClickHouse, ES, LangFuse)
├── .env.example                 # Environment variables template
├── requirements.txt             # Python dependencies
├── README.md                    # This file
│
├── src/
│   ├── config.py               # Settings and configuration
│   │
│   ├── storage/                # Database clients
│   │   ├── redis_client_v2.py
│   │   ├── clickhouse_client_v2.py
│   │   └── elasticsearch_client_v2.py
│   │
│   ├── agent/                  # LangGraph AI Agent
│   │   ├── state.py            # Agent state management
│   │   ├── nodes.py            # 6 workflow nodes
│   │   ├── graph.py            # LangGraph workflow builder
│   │   ├── orchestrator.py    # Main agent orchestrator
│   │   │
│   │   ├── tools/              # 11 agent tools
│   │   │   ├── schemas.py      # Pydantic schemas for tools
│   │   │   ├── eaos_tools.py
│   │   │   ├── trend_tools.py
│   │   │   ├── search_tools.py
│   │   │   ├── anomaly_tools.py
│   │   │   └── recommendation_tools.py
│   │   │
│   │   └── prompts/            # System prompts
│   │       ├── system_prompt.py
│   │       └── few_shot_examples.py
│   │
│   ├── api/                    # FastAPI REST API
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── schemas.py          # Request/response models
│   │   ├── dependencies.py     # Cache, retry, rate limit decorators
│   │   │
│   │   └── routes/             # API endpoints
│   │       ├── health.py       # Health check
│   │       ├── chat.py         # Chat with agent
│   │       ├── eaos.py         # EAOS endpoints
│   │       └── trends.py       # Trends endpoint
│   │
│   └── monitoring/             # Observability
│       └── langfuse_setup.py   # LangFuse integration
│
└── scripts/
    ├── clickhouse-init/        # ClickHouse init SQL
    │   ├── 001_create_tables.sql
    │   └── 002_updated_schema.sql
    │
    ├── seed_sample_data.py     # Seed databases with test data
    └── test_e2e.py             # End-to-end tests
```

## 🚢 Production Deployment

### Recommendations for Production

1. **Use Cloud Services:**
   - Replace self-hosted ClickHouse with ClickHouse Cloud
   - Use Google Cloud Memorystore for Redis
   - Use Elastic Cloud for Elasticsearch
   - Use LangFuse Cloud instead of self-hosted

2. **Security:**
   - Enable authentication on all databases
   - Use secrets manager for credentials (GCP Secret Manager)
   - Enable TLS/SSL on all connections
   - Add API authentication (JWT tokens)

3. **Scaling:**
   - Deploy FastAPI on Cloud Run or GKE
   - Use Cloud Load Balancer
   - Enable horizontal pod autoscaling
   - Separate read and write replicas

4. **Monitoring:**
   - Enable Cloud Monitoring and Logging
   - Set up alerts for high error rates
   - Monitor LLM costs in LangFuse dashboard
   - Track API response times

5. **Cost Optimization:**
   - Use Gemini Flash for simple queries
   - Implement aggressive caching
   - Set rate limits per user
   - Archive old data to Cloud Storage

## 📝 License

MIT License

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

## 📧 Support

For issues or questions, please open a GitHub issue.

---

**Built with ❤️ for SE363 Final Project - UIT**

*Developed using LangChain, LangGraph, and Vertex AI*
