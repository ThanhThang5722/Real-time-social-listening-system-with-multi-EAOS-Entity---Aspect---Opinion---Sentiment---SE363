"""Agent tools for EAOS queries"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from langchain.tools import tool
import structlog

from src.storage.redis_client import redis_client
from src.storage.clickhouse_client import clickhouse_client
from src.agent.tools.schemas import (
    GetCurrentEAOSInput,
    GetEAOSTimelineInput,
    EAOSScoreOutput,
    EAOSTimelineOutput,
    EAOSTimelinePoint,
    Granularity
)

logger = structlog.get_logger(__name__)


@tool
async def get_current_eaos(program_id: str) -> Dict[str, Any]:
    """
    Get current EAOS (Engagement-Adjusted Opinion Score) for a program/entity.

    This tool retrieves the most recent EAOS score, which combines sentiment
    and engagement metrics. Higher scores indicate better audience reception.

    Args:
        program_id: Program or entity identifier (e.g., "contestant_1", "segment_intro")

    Returns:
        Dictionary with:
        - score: EAOS score (0-1, higher is better)
        - positive_pct: Percentage of positive comments
        - negative_pct: Percentage of negative comments
        - total_comments: Total comment count used
        - timestamp: When score was calculated

    Example:
        >>> result = await get_current_eaos("contestant_1")
        >>> print(f"EAOS: {result['score']:.2f}")
    """
    try:
        logger.info("Getting current EAOS", program_id=program_id)

        # Try Redis cache first (fast)
        cached_score = await redis_client.get_eaos_score(program_id)

        if cached_score:
            metadata = cached_score.get('metadata', {})
            score = cached_score['score']

            # Calculate sentiment percentages from metadata if available
            comment_count = metadata.get('comment_count', 0)

            return {
                "score": round(score, 4),
                "positive_pct": 0.0,  # Would need to track this separately
                "negative_pct": 0.0,
                "total_comments": comment_count,
                "timestamp": datetime.now()
            }

        # Fallback to ClickHouse (slower but authoritative)
        scores = clickhouse_client.get_current_eaos(
            entities=[program_id],
            time_window_minutes=5
        )

        if not scores:
            logger.warning("No EAOS data found", program_id=program_id)
            return {
                "score": 0.0,
                "positive_pct": 0.0,
                "negative_pct": 0.0,
                "total_comments": 0,
                "timestamp": datetime.now(),
                "error": "No data available"
            }

        score_data = scores[0]

        # Get sentiment distribution for percentages
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)

        sentiment_dist = clickhouse_client.get_sentiment_distribution(
            start_time=start_time,
            end_time=end_time
        )

        total = sum(sentiment_dist.values())
        positive_pct = (sentiment_dist.get('positive', 0) / total * 100) if total > 0 else 0
        negative_pct = (sentiment_dist.get('negative', 0) / total * 100) if total > 0 else 0

        return {
            "score": round(score_data['eaos_score'], 4),
            "positive_pct": round(positive_pct, 2),
            "negative_pct": round(negative_pct, 2),
            "total_comments": score_data['comment_count'],
            "timestamp": score_data['timestamp']
        }

    except Exception as e:
        logger.error("Failed to get current EAOS", program_id=program_id, error=str(e))
        return {
            "score": 0.0,
            "positive_pct": 0.0,
            "negative_pct": 0.0,
            "total_comments": 0,
            "timestamp": datetime.now(),
            "error": str(e)
        }


@tool
async def get_eaos_timeline(
    program_id: str,
    from_time: str,
    to_time: str,
    granularity: str = "5min"
) -> Dict[str, Any]:
    """
    Get EAOS score timeline for a program over a time period.

    This tool retrieves historical EAOS scores to show trends and patterns
    over time. Useful for understanding audience reaction changes.

    Args:
        program_id: Program or entity identifier
        from_time: Start time (ISO format: "2024-01-01T10:00:00")
        to_time: End time (ISO format)
        granularity: Time granularity - "minute", "5min", or "segment"

    Returns:
        Dictionary with:
        - timeline: List of {timestamp, score, comment_count}
        - program_id: Entity identifier
        - granularity: Time granularity used

    Example:
        >>> result = await get_eaos_timeline(
        ...     "contestant_1",
        ...     "2024-01-01T19:00:00",
        ...     "2024-01-01T20:00:00",
        ...     "5min"
        ... )
        >>> for point in result['timeline']:
        ...     print(f"{point['timestamp']}: {point['score']:.2f}")
    """
    try:
        logger.info(
            "Getting EAOS timeline",
            program_id=program_id,
            from_time=from_time,
            to_time=to_time,
            granularity=granularity
        )

        # Parse datetime strings
        start_dt = datetime.fromisoformat(from_time)
        end_dt = datetime.fromisoformat(to_time)

        # Map granularity to time window minutes
        granularity_map = {
            "minute": 1,
            "5min": 5,
            "segment": 15  # Assume segments are ~15 minutes
        }
        time_window = granularity_map.get(granularity, 5)

        # Query ClickHouse
        timeline_data = clickhouse_client.get_eaos_timeline(
            entity=program_id,
            start_time=start_dt,
            end_time=end_dt,
            time_window_minutes=time_window
        )

        if not timeline_data:
            logger.warning("No timeline data found", program_id=program_id)
            return {
                "timeline": [],
                "program_id": program_id,
                "granularity": granularity
            }

        # Format timeline
        timeline = [
            {
                "timestamp": point['timestamp'],
                "score": round(point['eaos_score'], 4),
                "comment_count": point['comment_count']
            }
            for point in timeline_data
        ]

        return {
            "timeline": timeline,
            "program_id": program_id,
            "granularity": granularity
        }

    except Exception as e:
        logger.error(
            "Failed to get EAOS timeline",
            program_id=program_id,
            error=str(e)
        )
        return {
            "timeline": [],
            "program_id": program_id,
            "granularity": granularity,
            "error": str(e)
        }


# Convenience function to run async tools from sync context
def run_async_tool(coro):
    """Helper to run async tool in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
