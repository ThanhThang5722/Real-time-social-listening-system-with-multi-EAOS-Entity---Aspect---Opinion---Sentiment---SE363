"""Health check endpoint"""

from fastapi import APIRouter
from datetime import datetime
import structlog

from src.api.schemas import HealthStatus
from src.storage.redis_client_v2 import redis_client_v2
from src.storage.clickhouse_client_v2 import clickhouse_client_v2
from src.storage.elasticsearch_client_v2 import elasticsearch_client_v2
from src.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Health check endpoint

    Checks connectivity to all backend services:
    - Redis (caching)
    - ClickHouse (analytics)
    - Elasticsearch (search)

    **Status levels:**
    - healthy: All services operational
    - degraded: Some services down but core functionality works
    - unhealthy: Critical services down
    """
    services_status = {}
    critical_services_down = 0
    non_critical_services_down = 0

    # Check Redis
    try:
        await redis_client_v2.client.ping()
        services_status['redis'] = 'healthy'
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        services_status['redis'] = 'unhealthy'
        non_critical_services_down += 1  # Redis is for caching, not critical

    # Check ClickHouse
    try:
        clickhouse_client_v2.client.command("SELECT 1")
        services_status['clickhouse'] = 'healthy'
    except Exception as e:
        logger.error("ClickHouse health check failed", error=str(e))
        services_status['clickhouse'] = 'unhealthy'
        critical_services_down += 1  # ClickHouse is critical for analytics

    # Check Elasticsearch
    try:
        info = await elasticsearch_client_v2.client.info()
        services_status['elasticsearch'] = 'healthy'
    except Exception as e:
        logger.warning("Elasticsearch health check failed", error=str(e))
        services_status['elasticsearch'] = 'unhealthy'
        non_critical_services_down += 1  # ES is for search, not critical for basic queries

    # Determine overall status
    if critical_services_down > 0:
        overall_status = 'unhealthy'
    elif non_critical_services_down > 0:
        overall_status = 'degraded'
    else:
        overall_status = 'healthy'

    # Log health check result
    logger.info(
        "Health check completed",
        status=overall_status,
        services=services_status
    )

    return HealthStatus(
        status=overall_status,
        timestamp=datetime.now(),
        services=services_status,
        version="1.0.0"
    )
