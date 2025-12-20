"""Agent tools for trending topics analysis"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from langchain.tools import tool
import structlog

from src.storage.redis_client import redis_client
from src.storage.clickhouse_client import clickhouse_client
from src.agent.tools.schemas import (
    GetTrendingTopicsInput,
    TrendingTopicsOutput,
    TrendingTopic,
    TrendDirection,
    TimeRange
)

logger = structlog.get_logger(__name__)


def calculate_trend_direction(
    current_count: int,
    previous_count: int,
    threshold: float = 1.5
) -> str:
    """
    Calculate trend direction based on count changes

    Args:
        current_count: Current mention count
        previous_count: Previous period mention count
        threshold: Spike threshold multiplier

    Returns:
        Trend direction: rising, falling, stable, or spike
    """
    if previous_count == 0:
        return "spike" if current_count > 10 else "rising"

    ratio = current_count / previous_count

    if ratio >= threshold * 2:
        return "spike"
    elif ratio >= threshold:
        return "rising"
    elif ratio <= (1 / threshold):
        return "falling"
    else:
        return "stable"


@tool
async def get_trending_topics(
    limit: int = 10,
    time_range: str = "15min"
) -> Dict[str, Any]:
    """
    Get currently trending topics/keywords with sentiment and trend direction.

    This tool identifies what topics are being discussed most in recent comments.
    Useful for understanding what's capturing audience attention.

    Args:
        limit: Maximum number of topics to return (1-50)
        time_range: Time range to analyze - "5min", "15min", or "1hour"

    Returns:
        Dictionary with:
        - topics: List of trending topics with:
          - topic: Topic/keyword text
          - count: Number of mentions
          - sentiment: Average sentiment score
          - trend_direction: "rising", "falling", "stable", or "spike"
        - time_range: Time range used
        - timestamp: When data was retrieved

    Example:
        >>> result = await get_trending_topics(limit=5, time_range="15min")
        >>> for topic in result['topics']:
        ...     print(f"{topic['topic']}: {topic['count']} mentions ({topic['trend_direction']})")
    """
    try:
        logger.info("Getting trending topics", limit=limit, time_range=time_range)

        # Map time range to minutes
        time_map = {
            "5min": 5,
            "15min": 15,
            "1hour": 60
        }
        time_window_minutes = time_map.get(time_range, 15)

        # Try Redis cache first (fast)
        cached_trends = await redis_client.get_trending_topics(
            time_window=time_window_minutes,
            limit=limit
        )

        if cached_trends:
            # Get sentiment from ClickHouse for cached topics
            topics_list = [t['topic'] for t in cached_trends]

            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=time_window_minutes)

            # Get previous period for trend direction
            prev_start = start_time - timedelta(minutes=time_window_minutes)

            topics_data = []

            for trend in cached_trends[:limit]:
                topic = trend['topic']
                current_count = trend['mentions']

                # Get sentiment from ClickHouse
                # Simplified: use average sentiment for entity
                top_entities = clickhouse_client.get_top_entities(
                    start_time=start_time,
                    end_time=end_time,
                    limit=100
                )

                sentiment = 0.0
                for entity in top_entities:
                    if entity['entity'] == topic:
                        sentiment = entity['avg_sentiment']
                        break

                # Calculate trend direction (simplified)
                trend_direction = "rising"  # Would need historical comparison

                topics_data.append({
                    "topic": topic,
                    "count": current_count,
                    "sentiment": round(sentiment, 3),
                    "trend_direction": trend_direction
                })

            return {
                "topics": topics_data,
                "time_range": time_range,
                "timestamp": datetime.now()
            }

        # Fallback to ClickHouse aggregation
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=time_window_minutes)

        top_entities = clickhouse_client.get_top_entities(
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        topics_data = []
        for entity in top_entities:
            topics_data.append({
                "topic": entity['entity'],
                "count": entity['mention_count'],
                "sentiment": round(entity['avg_sentiment'], 3),
                "trend_direction": "stable"
            })

        return {
            "topics": topics_data,
            "time_range": time_range,
            "timestamp": datetime.now()
        }

    except Exception as e:
        logger.error("Failed to get trending topics", error=str(e))
        return {
            "topics": [],
            "time_range": time_range,
            "timestamp": datetime.now(),
            "error": str(e)
        }


@tool
async def get_topic_details(topic: str, time_range: str = "15min") -> Dict[str, Any]:
    """
    Get detailed information about a specific trending topic.

    Args:
        topic: Topic/keyword to analyze
        time_range: Time range - "5min", "15min", or "1hour"

    Returns:
        Dictionary with topic statistics and sample comments
    """
    try:
        logger.info("Getting topic details", topic=topic, time_range=time_range)

        time_map = {"5min": 5, "15min": 15, "1hour": 60}
        minutes = time_map.get(time_range, 15)

        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=minutes)

        # Search comments mentioning this topic
        comments = clickhouse_client.search_comments(
            query=topic,
            start_time=start_time,
            end_time=end_time,
            limit=20
        )

        # Calculate stats
        total = len(comments)
        positive = sum(1 for c in comments if c['sentiment'] == 'positive')
        negative = sum(1 for c in comments if c['sentiment'] == 'negative')
        neutral = sum(1 for c in comments if c['sentiment'] == 'neutral')

        avg_sentiment = (
            sum(c['sentiment_score'] for c in comments) / total
            if total > 0 else 0.0
        )

        return {
            "topic": topic,
            "time_range": time_range,
            "total_mentions": total,
            "sentiment_distribution": {
                "positive": positive,
                "negative": negative,
                "neutral": neutral
            },
            "avg_sentiment": round(avg_sentiment, 3),
            "sample_comments": [
                {
                    "text": c['text'][:100] + "..." if len(c['text']) > 100 else c['text'],
                    "sentiment": c['sentiment'],
                    "timestamp": c['timestamp']
                }
                for c in comments[:5]
            ]
        }

    except Exception as e:
        logger.error("Failed to get topic details", topic=topic, error=str(e))
        return {
            "topic": topic,
            "error": str(e)
        }
