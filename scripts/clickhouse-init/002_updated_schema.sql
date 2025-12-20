-- TV Producer Analytics - Updated ClickHouse Schema
-- Aligned with specifications

-- Drop old tables if exist (for clean migration)
DROP TABLE IF EXISTS tv_analytics.comments;
DROP TABLE IF EXISTS tv_analytics.eaos_metrics;
DROP TABLE IF EXISTS tv_analytics.trending_topics;
DROP TABLE IF EXISTS tv_analytics.sentiment_distribution_mv;
DROP TABLE IF EXISTS tv_analytics.entity_mentions_hourly_mv;

-- ============================================
-- Table 1: eaos_metrics
-- Stores EAOS scores over time per program
-- ============================================
CREATE TABLE IF NOT EXISTS tv_analytics.eaos_metrics (
    program_id String,
    timestamp DateTime,
    score Float32,
    positive_count UInt32,
    negative_count UInt32,
    neutral_count UInt32,
    total_comments UInt32,

    -- Indexes
    INDEX idx_program_id program_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (program_id, timestamp)
TTL timestamp + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- ============================================
-- Table 2: comment_aggregates
-- Aggregated comment data by topic
-- ============================================
CREATE TABLE IF NOT EXISTS tv_analytics.comment_aggregates (
    program_id String,
    timestamp DateTime,
    topic String,
    count UInt32,
    avg_sentiment Float32,

    INDEX idx_program_id program_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_topic topic TYPE bloom_filter GRANULARITY 4,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (program_id, timestamp, topic)
TTL timestamp + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- ============================================
-- Table 3: anomalies
-- Detected anomalies in metrics
-- ============================================
CREATE TABLE IF NOT EXISTS tv_analytics.anomalies (
    program_id String,
    timestamp DateTime,
    metric LowCardinality(String),  -- 'eaos', 'volume', 'sentiment'
    value Float32,
    expected Float32,
    deviation Float32,
    severity LowCardinality(String),  -- 'low', 'medium', 'high', 'critical'

    INDEX idx_program_id program_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_metric metric TYPE set(3) GRANULARITY 4,
    INDEX idx_severity severity TYPE set(4) GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (program_id, timestamp)
TTL timestamp + INTERVAL 7 DAY
SETTINGS index_granularity = 8192;

-- ============================================
-- Table 4: raw_comments (for detailed storage)
-- Optional: Keep raw comments for detailed analysis
-- ============================================
CREATE TABLE IF NOT EXISTS tv_analytics.raw_comments (
    comment_id String,
    program_id String,
    text String,
    username String,
    timestamp DateTime,
    sentiment LowCardinality(String),
    sentiment_score Float32,
    engagement_score UInt32,
    topics Array(String),
    metadata String,  -- JSON string for flexibility

    INDEX idx_program_id program_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1,
    INDEX idx_sentiment sentiment TYPE set(3) GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (program_id, timestamp, comment_id)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- ============================================
-- Materialized Views for Real-time Aggregation
-- ============================================

-- View 1: Aggregate EAOS metrics per 5-minute window
CREATE MATERIALIZED VIEW IF NOT EXISTS tv_analytics.eaos_5min_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(window_start)
ORDER BY (program_id, window_start)
AS SELECT
    program_id,
    toStartOfFiveMinutes(timestamp) AS window_start,
    countIf(sentiment = 'positive') AS positive_count,
    countIf(sentiment = 'negative') AS negative_count,
    countIf(sentiment = 'neutral') AS neutral_count,
    count() AS total_comments,
    avg(sentiment_score) AS avg_sentiment_score,
    avg(engagement_score) AS avg_engagement_score
FROM tv_analytics.raw_comments
GROUP BY program_id, window_start;

-- View 2: Topic aggregates per hour
CREATE MATERIALIZED VIEW IF NOT EXISTS tv_analytics.topic_hourly_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour_start)
ORDER BY (program_id, hour_start, topic)
AS SELECT
    program_id,
    toStartOfHour(timestamp) AS hour_start,
    arrayJoin(topics) AS topic,
    count() AS count,
    avg(sentiment_score) AS avg_sentiment
FROM tv_analytics.raw_comments
WHERE length(topics) > 0
GROUP BY program_id, hour_start, topic;
