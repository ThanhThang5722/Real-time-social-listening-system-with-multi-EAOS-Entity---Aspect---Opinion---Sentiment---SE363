"""Trends endpoints for hot topics"""

from fastapi import APIRouter, Query
from datetime import datetime
import structlog

from src.api.schemas import TrendsResponse, TrendingTopic, ErrorResponse
from src.api.dependencies import cache_manager, with_retry
from src.storage.redis_client_v2 import redis_client_v2

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["trends"])


@router.get("/trends", response_model=TrendsResponse)
@cache_manager.cached(prefix="trends", ttl=60)  # 60 second cache
@with_retry(max_retries=3, delay=0.5)
async def get_trending_topics(
    limit: int = Query(10, ge=1, le=50, description="Number of topics to return"),
    time_range: str = Query("15min", description="Time range: 5min, 15min, 1hour")
):
    """
    Get currently trending topics

    Returns the hottest topics/keywords being discussed by viewers.
    Topics are ranked by mention count (score).

    **Cache:** 60 seconds TTL

    **Parameters:**
    - limit: Max topics to return (1-50)
    - time_range: Time window (5min, 15min, 1hour)

    **Returns:**
    List of trending topics with scores and rankings
    """
    try:
        logger.info("Fetching trending topics", limit=limit, time_range=time_range)

        # Get trends from Redis
        trends_data = await redis_client_v2.get_top_trends(
            time_range=time_range,
            limit=limit
        )

        if not trends_data:
            logger.warning("No trends found", time_range=time_range)
            # Return empty trends instead of error
            return TrendsResponse(
                trends=[],
                time_range=time_range,
                timestamp=datetime.now()
            )

        # Format trends with rankings
        trending_topics = [
            TrendingTopic(
                topic=trend['topic'],
                score=trend['score'],
                rank=idx + 1
            )
            for idx, trend in enumerate(trends_data)
        ]

        logger.info("Trends retrieved", count=len(trending_topics), time_range=time_range)

        return TrendsResponse(
            trends=trending_topics,
            time_range=time_range,
            timestamp=datetime.now()
        )

    except Exception as e:
        logger.error("Failed to get trends", time_range=time_range, error=str(e))
        # Return empty trends on error (graceful degradation)
        return TrendsResponse(
            trends=[],
            time_range=time_range,
            timestamp=datetime.now()
        )
