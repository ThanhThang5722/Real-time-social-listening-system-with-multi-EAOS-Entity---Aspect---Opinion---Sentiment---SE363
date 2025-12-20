-- TV Producer Analytics - ClickHouse Schema
-- Time-series tables for comments and EAOS metrics

-- Comments table with EAOS analysis
CREATE TABLE IF NOT EXISTS tv_analytics.comments (
    comment_id String,
    text String,
    username String,
    timestamp DateTime,
    sentiment LowCardinality(String),  -- 'positive', 'negative', 'neutral'
    sentiment_score Float32,
    entities Array(String),
    metadata Map(String, String),

    -- Indexes
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1,
    INDEX idx_sentiment sentiment TYPE set(3) GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, comment_id)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- EAOS metrics table (aggregated per time window)
CREATE TABLE IF NOT EXISTS tv_analytics.eaos_metrics (
    entity String,
    timestamp DateTime,
    eaos_score Float32,
    sentiment_score Float32,
    engagement_score Float32,
    comment_count UInt32,
    time_window_minutes UInt16,

    -- Indexes
    INDEX idx_entity entity TYPE bloom_filter GRANULARITY 4,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (entity, time_window_minutes, timestamp)
TTL timestamp + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- Trending topics table
CREATE TABLE IF NOT EXISTS tv_analytics.trending_topics (
    topic String,
    timestamp DateTime,
    mention_count UInt32,
    time_window_minutes UInt16,
    avg_sentiment Float32,
    related_entities Array(String),

    INDEX idx_topic topic TYPE bloom_filter GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (time_window_minutes, timestamp, mention_count)
TTL timestamp + INTERVAL 7 DAY
SETTINGS index_granularity = 8192;

-- Materialized view for sentiment distribution per minute
CREATE MATERIALIZED VIEW IF NOT EXISTS tv_analytics.sentiment_distribution_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(timestamp_minute)
ORDER BY (timestamp_minute, sentiment)
AS SELECT
    toStartOfMinute(timestamp) AS timestamp_minute,
    sentiment,
    count() AS comment_count,
    avg(sentiment_score) AS avg_score
FROM tv_analytics.comments
GROUP BY timestamp_minute, sentiment;

-- Materialized view for entity mentions per hour
CREATE MATERIALIZED VIEW IF NOT EXISTS tv_analytics.entity_mentions_hourly_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(timestamp_hour)
ORDER BY (timestamp_hour, entity)
AS SELECT
    toStartOfHour(timestamp) AS timestamp_hour,
    arrayJoin(entities) AS entity,
    count() AS mention_count,
    avg(sentiment_score) AS avg_sentiment
FROM tv_analytics.comments
GROUP BY timestamp_hour, entity;
