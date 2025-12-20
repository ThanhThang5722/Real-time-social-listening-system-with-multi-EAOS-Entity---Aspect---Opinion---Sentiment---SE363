"""EAOS endpoints for querying scores"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
import structlog

from src.api.schemas import EAOSCurrent, EAOSTimelineResponse, EAOSTimelinePoint, ErrorResponse
from src.api.dependencies import cache_manager, with_retry
from src.storage.redis_client_v2 import redis_client_v2
from src.storage.clickhouse_client_v2 import clickhouse_client_v2

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/eaos", tags=["eaos"])


@router.get("/current/{program_id}", response_model=EAOSCurrent, responses={404: {"model": ErrorResponse}})
@cache_manager.cached(prefix="eaos_current", ttl=30)  # 30 second cache
@with_retry(max_retries=3, delay=0.5)
async def get_current_eaos(program_id: str):
    """
    Get current EAOS score for a program

    Returns the most recent EAOS (Engagement-Adjusted Opinion Score) which combines
    sentiment analysis and engagement metrics.

    **Cache:** 30 seconds TTL

    **Returns:**
    - score: EAOS score (0-1, higher is better)
    - positive/negative/neutral: Comment counts
    - total: Total comments analyzed
    - updated_at: Last update timestamp
    """
    try:
        logger.info("Fetching current EAOS", program_id=program_id)

        # Try Redis first (fast)
        eaos_data = await redis_client_v2.get_current_eaos(program_id)

        if eaos_data:
            return EAOSCurrent(
                program_id=program_id,
                score=eaos_data['score'],
                positive=eaos_data['positive'],
                negative=eaos_data['negative'],
                neutral=eaos_data['neutral'],
                total=eaos_data['total'],
                updated_at=datetime.fromisoformat(eaos_data['updated_at'])
            )

        # Fallback to ClickHouse
        latest_eaos = clickhouse_client_v2.get_latest_eaos(program_id)

        if not latest_eaos:
            raise HTTPException(
                status_code=404,
                detail=f"No EAOS data found for program '{program_id}'"
            )

        return EAOSCurrent(
            program_id=program_id,
            score=latest_eaos['score'],
            positive=latest_eaos['positive_count'],
            negative=latest_eaos['negative_count'],
            neutral=latest_eaos['neutral_count'],
            total=latest_eaos['total_comments'],
            updated_at=latest_eaos['timestamp']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get current EAOS", program_id=program_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve EAOS data: {str(e)}"
        )


@router.get("/timeline/{program_id}", response_model=EAOSTimelineResponse)
@cache_manager.cached(prefix="eaos_timeline", ttl=60)  # 60 second cache
@with_retry(max_retries=3, delay=0.5)
async def get_eaos_timeline(
    program_id: str,
    from_time: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    to_time: Optional[datetime] = Query(None, description="End time (ISO format)"),
    granularity: str = Query("5min", description="Time granularity: minute, 5min, segment")
):
    """
    Get EAOS timeline for a program over time

    Shows how EAOS score changed over time, useful for understanding
    audience reaction trends.

    **Cache:** 60 seconds TTL

    **Parameters:**
    - from_time: Start time (default: 1 hour ago)
    - to_time: End time (default: now)
    - granularity: Time granularity (default: 5min)

    **Returns:**
    Timeline of EAOS scores with sentiment breakdown
    """
    try:
        # Default time range: last hour
        if not to_time:
            to_time = datetime.now()
        if not from_time:
            from_time = to_time - timedelta(hours=1)

        logger.info(
            "Fetching EAOS timeline",
            program_id=program_id,
            from_time=from_time,
            to_time=to_time,
            granularity=granularity
        )

        # Get timeline from ClickHouse
        timeline_data = clickhouse_client_v2.get_eaos_timeline(
            program_id=program_id,
            start_time=from_time,
            end_time=to_time
        )

        if not timeline_data:
            logger.warning("No timeline data found", program_id=program_id)
            # Return empty timeline instead of error
            return EAOSTimelineResponse(
                program_id=program_id,
                timeline=[],
                granularity=granularity,
                from_time=from_time,
                to_time=to_time
            )

        # Format timeline points
        timeline_points = [
            EAOSTimelinePoint(
                timestamp=point['timestamp'],
                score=point['score'],
                positive_count=point['positive_count'],
                negative_count=point['negative_count'],
                neutral_count=point['neutral_count'],
                total_comments=point['total_comments']
            )
            for point in timeline_data
        ]

        return EAOSTimelineResponse(
            program_id=program_id,
            timeline=timeline_points,
            granularity=granularity,
            from_time=from_time,
            to_time=to_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get EAOS timeline", program_id=program_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve timeline: {str(e)}"
        )
