"""Initialize all databases with schemas and indexes"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from src.config import settings
from src.storage.redis_client import redis_client
from src.storage.clickhouse_client import clickhouse_client
from src.storage.elasticsearch_client import elasticsearch_client
import structlog

logger = structlog.get_logger(__name__)


async def init_redis():
    """Initialize Redis - clear test data"""
    logger.info("Initializing Redis...")
    try:
        await redis_client.connect()
        # Clear any test data
        await redis_client.clear_pattern("eaos:*")
        await redis_client.clear_pattern("trend:*")
        await redis_client.clear_pattern("metrics:*")
        logger.info("Redis initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize Redis", error=str(e))
        raise


def init_clickhouse():
    """Initialize ClickHouse - tables already created via init scripts"""
    logger.info("Initializing ClickHouse...")
    try:
        clickhouse_client.connect()

        # Test tables exist
        result = clickhouse_client.client.query(
            "SHOW TABLES FROM tv_analytics"
        )
        tables = [row[0] for row in result.result_rows]

        expected_tables = ['comments', 'eaos_metrics', 'trending_topics']
        for table in expected_tables:
            if table in tables:
                logger.info(f"Table '{table}' exists")
            else:
                logger.warning(f"Table '{table}' not found")

        logger.info("ClickHouse initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize ClickHouse", error=str(e))
        raise


async def init_elasticsearch():
    """Initialize Elasticsearch - create indices"""
    logger.info("Initializing Elasticsearch...")
    try:
        await elasticsearch_client.connect()
        # Indices are created automatically in connect()
        logger.info("Elasticsearch initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize Elasticsearch", error=str(e))
        raise


async def main():
    """Initialize all databases"""
    logger.info("Starting database initialization...")

    try:
        # Initialize Redis
        await init_redis()

        # Initialize ClickHouse
        init_clickhouse()

        # Initialize Elasticsearch
        await init_elasticsearch()

        logger.info("All databases initialized successfully!")

        # Cleanup
        await redis_client.disconnect()
        clickhouse_client.disconnect()
        await elasticsearch_client.disconnect()

    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    # Setup basic logging
    import structlog
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )

    asyncio.run(main())
