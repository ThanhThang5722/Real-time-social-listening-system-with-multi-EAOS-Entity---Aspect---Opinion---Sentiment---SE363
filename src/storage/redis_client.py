"""Redis client for real-time caching and metrics"""

import json
from typing import Optional, Dict, List, Any
from datetime import timedelta
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


class RedisClient:
    """Async Redis client for caching EAOS scores and trends"""

    def __init__(self):
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection pool"""
        try:
            self.pool = ConnectionPool.from_url(
                settings.redis_url,
                decode_responses=settings.redis_decode_responses,
                max_connections=50,
            )
            self.client = redis.Redis(connection_pool=self.pool)
            await self.client.ping()
            logger.info("Redis connected successfully", host=settings.redis_host)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis disconnected")

    # ----------------------------------------
    # EAOS Operations
    # ----------------------------------------

    async def set_eaos_score(
        self,
        entity: str,
        score: float,
        ttl: int = 3600,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Cache EAOS score for an entity

        Args:
            entity: Entity name (e.g., "contestant_1", "segment_intro")
            score: EAOS score value
            ttl: Time-to-live in seconds (default 1 hour)
            metadata: Additional metadata (timestamp, sample size, etc.)
        """
        try:
            key = f"eaos:{entity}"
            data = {
                "score": score,
                "metadata": metadata or {}
            }
            await self.client.setex(
                key,
                ttl,
                json.dumps(data)
            )
            logger.debug("EAOS score cached", entity=entity, score=score)
            return True
        except Exception as e:
            logger.error("Failed to cache EAOS score", entity=entity, error=str(e))
            return False

    async def get_eaos_score(self, entity: str) -> Optional[Dict]:
        """Get cached EAOS score for an entity"""
        try:
            key = f"eaos:{entity}"
            data = await self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error("Failed to get EAOS score", entity=entity, error=str(e))
            return None

    async def get_all_eaos_scores(self) -> Dict[str, Dict]:
        """Get all cached EAOS scores"""
        try:
            keys = await self.client.keys("eaos:*")
            if not keys:
                return {}

            scores = {}
            for key in keys:
                entity = key.replace("eaos:", "")
                data = await self.client.get(key)
                if data:
                    scores[entity] = json.loads(data)

            return scores
        except Exception as e:
            logger.error("Failed to get all EAOS scores", error=str(e))
            return {}

    # ----------------------------------------
    # Trend Operations
    # ----------------------------------------

    async def add_trending_topic(
        self,
        topic: str,
        mentions: int,
        time_window: int,
        ttl: int = 3600
    ) -> bool:
        """
        Add trending topic with mentions count

        Args:
            topic: Topic/keyword
            mentions: Number of mentions in time window
            time_window: Time window in minutes
            ttl: Cache expiry in seconds
        """
        try:
            key = f"trend:{time_window}m"
            await self.client.zadd(
                key,
                {topic: mentions},
                nx=False  # Update if exists
            )
            await self.client.expire(key, ttl)
            logger.debug("Trending topic added", topic=topic, mentions=mentions)
            return True
        except Exception as e:
            logger.error("Failed to add trending topic", topic=topic, error=str(e))
            return False

    async def get_trending_topics(
        self,
        time_window: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top trending topics for a time window

        Args:
            time_window: Time window in minutes (5, 15, 60)
            limit: Max number of topics to return
        """
        try:
            key = f"trend:{time_window}m"
            # Get top topics with scores (mentions)
            topics = await self.client.zrevrange(
                key,
                0,
                limit - 1,
                withscores=True
            )

            return [
                {"topic": topic, "mentions": int(score)}
                for topic, score in topics
            ]
        except Exception as e:
            logger.error("Failed to get trending topics", error=str(e))
            return []

    async def increment_topic_count(
        self,
        topic: str,
        time_window: int,
        ttl: int = 3600
    ) -> int:
        """Increment mention count for a topic"""
        try:
            key = f"trend:{time_window}m"
            new_count = await self.client.zincrby(key, 1, topic)
            await self.client.expire(key, ttl)
            return int(new_count)
        except Exception as e:
            logger.error("Failed to increment topic count", topic=topic, error=str(e))
            return 0

    # ----------------------------------------
    # Time-series Metrics
    # ----------------------------------------

    async def push_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[int] = None,
        max_len: int = 1000
    ) -> bool:
        """
        Push a metric value to time-series list

        Args:
            metric_name: Name of the metric (e.g., "sentiment_avg")
            value: Metric value
            timestamp: Unix timestamp (default: current time)
            max_len: Max length of time-series (FIFO)
        """
        try:
            import time
            key = f"metrics:{metric_name}"
            ts = timestamp or int(time.time())

            await self.client.lpush(
                key,
                json.dumps({"value": value, "timestamp": ts})
            )
            await self.client.ltrim(key, 0, max_len - 1)
            return True
        except Exception as e:
            logger.error("Failed to push metric", metric=metric_name, error=str(e))
            return False

    async def get_metric_series(
        self,
        metric_name: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get recent metric values"""
        try:
            key = f"metrics:{metric_name}"
            data = await self.client.lrange(key, 0, limit - 1)
            return [json.loads(item) for item in data]
        except Exception as e:
            logger.error("Failed to get metric series", metric=metric_name, error=str(e))
            return []

    # ----------------------------------------
    # General Operations
    # ----------------------------------------

    async def set_json(
        self,
        key: str,
        value: Dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Set JSON value with optional TTL"""
        try:
            if ttl:
                await self.client.setex(key, ttl, json.dumps(value))
            else:
                await self.client.set(key, json.dumps(value))
            return True
        except Exception as e:
            logger.error("Failed to set JSON", key=key, error=str(e))
            return False

    async def get_json(self, key: str) -> Optional[Dict]:
        """Get JSON value"""
        try:
            data = await self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error("Failed to get JSON", key=key, error=str(e))
            return None

    async def delete(self, key: str) -> bool:
        """Delete a key"""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error("Failed to delete key", key=key, error=str(e))
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = await self.client.keys(pattern)
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info("Keys deleted", pattern=pattern, count=deleted)
                return deleted
            return 0
        except Exception as e:
            logger.error("Failed to clear pattern", pattern=pattern, error=str(e))
            return 0


# Global Redis client instance
redis_client = RedisClient()
