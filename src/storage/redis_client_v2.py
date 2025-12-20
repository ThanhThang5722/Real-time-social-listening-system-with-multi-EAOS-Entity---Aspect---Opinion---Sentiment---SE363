"""Updated Redis client matching new schema specifications"""

import json
from typing import Optional, Dict, List
from datetime import datetime
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


class RedisClientV2:
    """
    Redis client with schema:
    - eaos:current:{program_id} -> Hash {score, positive, negative, neutral, total, updated_at}
    - trends:top:{time_range} -> Sorted Set {topic: score}
    - events:{program_id}:{date} -> List of events
    """

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
    # EAOS Current Operations
    # Key: eaos:current:{program_id}
    # Type: Hash
    # ----------------------------------------

    async def set_current_eaos(
        self,
        program_id: str,
        score: float,
        positive: int,
        negative: int,
        neutral: int,
        total: int
    ) -> bool:
        """
        Set current EAOS for a program

        Args:
            program_id: Program identifier
            score: EAOS score (0-1)
            positive: Positive comment count
            negative: Negative comment count
            neutral: Neutral comment count
            total: Total comment count
        """
        try:
            key = f"eaos:current:{program_id}"

            data = {
                "score": str(score),
                "positive": str(positive),
                "negative": str(negative),
                "neutral": str(neutral),
                "total": str(total),
                "updated_at": datetime.now().isoformat()
            }

            await self.client.hset(key, mapping=data)
            await self.client.expire(key, 3600)  # 1 hour TTL

            logger.debug(
                "Current EAOS set",
                program_id=program_id,
                score=score,
                total=total
            )
            return True

        except Exception as e:
            logger.error("Failed to set current EAOS", program_id=program_id, error=str(e))
            return False

    async def get_current_eaos(self, program_id: str) -> Optional[Dict]:
        """
        Get current EAOS for a program

        Returns:
            Dict with keys: score, positive, negative, neutral, total, updated_at
        """
        try:
            key = f"eaos:current:{program_id}"
            data = await self.client.hgetall(key)

            if not data:
                return None

            return {
                "score": float(data.get("score", 0)),
                "positive": int(data.get("positive", 0)),
                "negative": int(data.get("negative", 0)),
                "neutral": int(data.get("neutral", 0)),
                "total": int(data.get("total", 0)),
                "updated_at": data.get("updated_at")
            }

        except Exception as e:
            logger.error("Failed to get current EAOS", program_id=program_id, error=str(e))
            return None

    async def get_all_current_eaos(self) -> Dict[str, Dict]:
        """Get all current EAOS scores"""
        try:
            pattern = "eaos:current:*"
            keys = await self.client.keys(pattern)

            if not keys:
                return {}

            scores = {}
            for key in keys:
                program_id = key.replace("eaos:current:", "")
                data = await self.get_current_eaos(program_id)
                if data:
                    scores[program_id] = data

            return scores

        except Exception as e:
            logger.error("Failed to get all current EAOS", error=str(e))
            return {}

    # ----------------------------------------
    # Trends Operations
    # Key: trends:top:{time_range}
    # Type: Sorted Set
    # ----------------------------------------

    async def add_trending_topic(
        self,
        time_range: str,
        topic: str,
        score: float
    ) -> bool:
        """
        Add topic to trending sorted set

        Args:
            time_range: Time range (5min, 15min, 1hour)
            topic: Topic/keyword
            score: Trending score (usually mention count)
        """
        try:
            key = f"trends:top:{time_range}"

            await self.client.zadd(key, {topic: score})
            await self.client.expire(key, 3600)

            logger.debug("Trending topic added", time_range=time_range, topic=topic, score=score)
            return True

        except Exception as e:
            logger.error("Failed to add trending topic", topic=topic, error=str(e))
            return False

    async def get_top_trends(self, time_range: str, limit: int = 10) -> List[Dict]:
        """
        Get top trending topics for time range

        Returns:
            List of {"topic": str, "score": float}
        """
        try:
            key = f"trends:top:{time_range}"

            # Get top topics with scores (highest first)
            results = await self.client.zrevrange(
                key,
                0,
                limit - 1,
                withscores=True
            )

            trends = [
                {"topic": topic, "score": score}
                for topic, score in results
            ]

            return trends

        except Exception as e:
            logger.error("Failed to get top trends", time_range=time_range, error=str(e))
            return []

    async def update_trending_scores_batch(
        self,
        time_range: str,
        topics: Dict[str, float]
    ) -> bool:
        """
        Batch update trending scores

        Args:
            time_range: Time range
            topics: Dict of {topic: score}
        """
        try:
            key = f"trends:top:{time_range}"

            if topics:
                await self.client.zadd(key, topics)
                await self.client.expire(key, 3600)

            return True

        except Exception as e:
            logger.error("Failed to update trending scores", error=str(e))
            return False

    # ----------------------------------------
    # Events Operations
    # Key: events:{program_id}:{date}
    # Type: List (JSON strings)
    # ----------------------------------------

    async def add_program_event(
        self,
        program_id: str,
        event_time: datetime,
        event_type: str,
        description: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add program event

        Args:
            program_id: Program identifier
            event_time: Event timestamp
            event_type: Event type (segment_change, anomaly, milestone)
            description: Event description
            metadata: Optional metadata
        """
        try:
            date_key = event_time.strftime("%Y-%m-%d")
            key = f"events:{program_id}:{date_key}"

            event = {
                "timestamp": event_time.isoformat(),
                "event_type": event_type,
                "description": description,
                "metadata": metadata or {}
            }

            await self.client.rpush(key, json.dumps(event))
            await self.client.expire(key, 86400 * 7)  # 7 days TTL

            logger.debug(
                "Program event added",
                program_id=program_id,
                event_type=event_type
            )
            return True

        except Exception as e:
            logger.error("Failed to add program event", program_id=program_id, error=str(e))
            return False

    async def get_program_events(
        self,
        program_id: str,
        date: datetime,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get program events for a date

        Returns:
            List of event dictionaries
        """
        try:
            date_key = date.strftime("%Y-%m-%d")
            key = f"events:{program_id}:{date_key}"

            event_strings = await self.client.lrange(key, 0, limit - 1)

            events = []
            for event_str in event_strings:
                try:
                    event = json.loads(event_str)
                    events.append(event)
                except json.JSONDecodeError:
                    continue

            return events

        except Exception as e:
            logger.error("Failed to get program events", program_id=program_id, error=str(e))
            return []

    async def get_recent_events(
        self,
        program_id: str,
        days: int = 1,
        limit: int = 50
    ) -> List[Dict]:
        """Get recent events across multiple days"""
        from datetime import timedelta

        all_events = []
        current_date = datetime.now()

        for i in range(days):
            date = current_date - timedelta(days=i)
            events = await self.get_program_events(program_id, date, limit)
            all_events.extend(events)

        # Sort by timestamp descending
        all_events.sort(key=lambda x: x['timestamp'], reverse=True)

        return all_events[:limit]

    # ----------------------------------------
    # Utility Operations
    # ----------------------------------------

    async def clear_program_data(self, program_id: str) -> int:
        """Clear all data for a program"""
        try:
            patterns = [
                f"eaos:current:{program_id}",
                f"events:{program_id}:*"
            ]

            deleted = 0
            for pattern in patterns:
                keys = await self.client.keys(pattern)
                if keys:
                    deleted += await self.client.delete(*keys)

            logger.info("Program data cleared", program_id=program_id, keys_deleted=deleted)
            return deleted

        except Exception as e:
            logger.error("Failed to clear program data", program_id=program_id, error=str(e))
            return 0

    async def clear_old_trends(self) -> int:
        """Clear all trend data (for cleanup)"""
        try:
            keys = await self.client.keys("trends:top:*")
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info("Trends cleared", count=deleted)
                return deleted
            return 0

        except Exception as e:
            logger.error("Failed to clear trends", error=str(e))
            return 0


# Global instance
redis_client_v2 = RedisClientV2()
