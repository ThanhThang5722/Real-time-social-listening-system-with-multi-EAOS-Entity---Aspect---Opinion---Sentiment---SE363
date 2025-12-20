"""ClickHouse client for time-series analytics storage"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import clickhouse_connect
from clickhouse_connect.driver import Client
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


class ClickHouseClient:
    """ClickHouse client for storing and querying time-series analytics data"""

    def __init__(self):
        self.client: Optional[Client] = None

    def connect(self):
        """Initialize ClickHouse connection"""
        try:
            self.client = clickhouse_connect.get_client(
                host=settings.clickhouse_host,
                port=settings.clickhouse_port,
                username=settings.clickhouse_username,
                password=settings.clickhouse_password,
                database=settings.clickhouse_database,
            )
            # Test connection
            self.client.command("SELECT 1")
            logger.info("ClickHouse connected successfully", host=settings.clickhouse_host)
        except Exception as e:
            logger.error("Failed to connect to ClickHouse", error=str(e))
            raise

    def disconnect(self):
        """Close ClickHouse connection"""
        if self.client:
            self.client.close()
            logger.info("ClickHouse disconnected")

    # ----------------------------------------
    # Comments Storage
    # ----------------------------------------

    def insert_comment(
        self,
        comment_id: str,
        text: str,
        username: str,
        timestamp: datetime,
        sentiment: str,
        sentiment_score: float,
        entities: List[str],
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Insert a single comment with EAOS analysis

        Args:
            comment_id: Unique comment identifier
            text: Comment text
            username: User who posted
            timestamp: Comment timestamp
            sentiment: Sentiment label (positive, negative, neutral)
            sentiment_score: Sentiment score (-1 to 1)
            entities: List of extracted entities
            metadata: Additional metadata (engagement, likes, etc.)
        """
        try:
            self.client.insert(
                "comments",
                [[
                    comment_id,
                    text,
                    username,
                    timestamp,
                    sentiment,
                    sentiment_score,
                    entities,
                    metadata or {}
                ]],
                column_names=[
                    "comment_id",
                    "text",
                    "username",
                    "timestamp",
                    "sentiment",
                    "sentiment_score",
                    "entities",
                    "metadata"
                ]
            )
            logger.debug("Comment inserted", comment_id=comment_id)
            return True
        except Exception as e:
            logger.error("Failed to insert comment", comment_id=comment_id, error=str(e))
            return False

    def insert_comments_batch(self, comments: List[Dict]) -> bool:
        """Insert multiple comments in batch"""
        try:
            data = []
            for comment in comments:
                data.append([
                    comment["comment_id"],
                    comment["text"],
                    comment["username"],
                    comment["timestamp"],
                    comment["sentiment"],
                    comment["sentiment_score"],
                    comment.get("entities", []),
                    comment.get("metadata", {})
                ])

            self.client.insert(
                "comments",
                data,
                column_names=[
                    "comment_id", "text", "username", "timestamp",
                    "sentiment", "sentiment_score", "entities", "metadata"
                ]
            )
            logger.info("Batch comments inserted", count=len(comments))
            return True
        except Exception as e:
            logger.error("Failed to insert comment batch", error=str(e))
            return False

    # ----------------------------------------
    # EAOS Metrics Storage
    # ----------------------------------------

    def insert_eaos_metric(
        self,
        entity: str,
        timestamp: datetime,
        eaos_score: float,
        sentiment_score: float,
        engagement_score: float,
        comment_count: int,
        time_window_minutes: int
    ) -> bool:
        """
        Insert EAOS metric for an entity at a specific time

        Args:
            entity: Entity name (contestant, segment, etc.)
            timestamp: Metric timestamp
            eaos_score: Calculated EAOS score
            sentiment_score: Average sentiment
            engagement_score: Engagement metric
            comment_count: Number of comments in window
            time_window_minutes: Time window size
        """
        try:
            self.client.insert(
                "eaos_metrics",
                [[
                    entity,
                    timestamp,
                    eaos_score,
                    sentiment_score,
                    engagement_score,
                    comment_count,
                    time_window_minutes
                ]],
                column_names=[
                    "entity", "timestamp", "eaos_score",
                    "sentiment_score", "engagement_score",
                    "comment_count", "time_window_minutes"
                ]
            )
            logger.debug("EAOS metric inserted", entity=entity, score=eaos_score)
            return True
        except Exception as e:
            logger.error("Failed to insert EAOS metric", entity=entity, error=str(e))
            return False

    # ----------------------------------------
    # Query Operations
    # ----------------------------------------

    def get_eaos_timeline(
        self,
        entity: str,
        start_time: datetime,
        end_time: datetime,
        time_window_minutes: int = 5
    ) -> List[Dict]:
        """
        Get EAOS score timeline for an entity

        Returns list of {timestamp, eaos_score, comment_count}
        """
        try:
            query = """
                SELECT
                    timestamp,
                    eaos_score,
                    sentiment_score,
                    engagement_score,
                    comment_count
                FROM eaos_metrics
                WHERE entity = %(entity)s
                    AND timestamp >= %(start_time)s
                    AND timestamp <= %(end_time)s
                    AND time_window_minutes = %(time_window)s
                ORDER BY timestamp ASC
            """

            result = self.client.query(
                query,
                parameters={
                    "entity": entity,
                    "start_time": start_time,
                    "end_time": end_time,
                    "time_window": time_window_minutes
                }
            )

            return [
                {
                    "timestamp": row[0],
                    "eaos_score": row[1],
                    "sentiment_score": row[2],
                    "engagement_score": row[3],
                    "comment_count": row[4]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to get EAOS timeline", entity=entity, error=str(e))
            return []

    def get_current_eaos(
        self,
        entities: Optional[List[str]] = None,
        time_window_minutes: int = 5
    ) -> List[Dict]:
        """
        Get most recent EAOS scores for entities

        Args:
            entities: List of entities (None = all)
            time_window_minutes: Time window to consider
        """
        try:
            if entities:
                entity_filter = f"AND entity IN {tuple(entities)}"
            else:
                entity_filter = ""

            query = f"""
                SELECT
                    entity,
                    eaos_score,
                    sentiment_score,
                    engagement_score,
                    comment_count,
                    timestamp
                FROM (
                    SELECT
                        entity,
                        eaos_score,
                        sentiment_score,
                        engagement_score,
                        comment_count,
                        timestamp,
                        ROW_NUMBER() OVER (PARTITION BY entity ORDER BY timestamp DESC) as rn
                    FROM eaos_metrics
                    WHERE time_window_minutes = %(time_window)s
                        {entity_filter}
                )
                WHERE rn = 1
                ORDER BY eaos_score DESC
            """

            result = self.client.query(
                query,
                parameters={"time_window": time_window_minutes}
            )

            return [
                {
                    "entity": row[0],
                    "eaos_score": row[1],
                    "sentiment_score": row[2],
                    "engagement_score": row[3],
                    "comment_count": row[4],
                    "timestamp": row[5]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to get current EAOS", error=str(e))
            return []

    def get_sentiment_distribution(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, int]:
        """Get sentiment distribution (positive/negative/neutral counts)"""
        try:
            query = """
                SELECT
                    sentiment,
                    COUNT(*) as count
                FROM comments
                WHERE timestamp >= %(start_time)s
                    AND timestamp <= %(end_time)s
                GROUP BY sentiment
            """

            result = self.client.query(
                query,
                parameters={
                    "start_time": start_time,
                    "end_time": end_time
                }
            )

            return {row[0]: row[1] for row in result.result_rows}
        except Exception as e:
            logger.error("Failed to get sentiment distribution", error=str(e))
            return {}

    def get_top_entities(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[Dict]:
        """Get most mentioned entities in time range"""
        try:
            query = """
                SELECT
                    entity,
                    COUNT(*) as mention_count,
                    AVG(sentiment_score) as avg_sentiment
                FROM comments
                ARRAY JOIN entities as entity
                WHERE timestamp >= %(start_time)s
                    AND timestamp <= %(end_time)s
                GROUP BY entity
                ORDER BY mention_count DESC
                LIMIT %(limit)s
            """

            result = self.client.query(
                query,
                parameters={
                    "start_time": start_time,
                    "end_time": end_time,
                    "limit": limit
                }
            )

            return [
                {
                    "entity": row[0],
                    "mention_count": row[1],
                    "avg_sentiment": row[2]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to get top entities", error=str(e))
            return []

    def search_comments(
        self,
        query: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        sentiment: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Search comments by text with optional filters"""
        try:
            conditions = ["positionCaseInsensitive(text, %(query)s) > 0"]
            params = {"query": query, "limit": limit}

            if start_time:
                conditions.append("timestamp >= %(start_time)s")
                params["start_time"] = start_time

            if end_time:
                conditions.append("timestamp <= %(end_time)s")
                params["end_time"] = end_time

            if sentiment:
                conditions.append("sentiment = %(sentiment)s")
                params["sentiment"] = sentiment

            where_clause = " AND ".join(conditions)

            sql = f"""
                SELECT
                    comment_id,
                    text,
                    username,
                    timestamp,
                    sentiment,
                    sentiment_score,
                    entities
                FROM comments
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT %(limit)s
            """

            result = self.client.query(sql, parameters=params)

            return [
                {
                    "comment_id": row[0],
                    "text": row[1],
                    "username": row[2],
                    "timestamp": row[3],
                    "sentiment": row[4],
                    "sentiment_score": row[5],
                    "entities": row[6]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to search comments", query=query, error=str(e))
            return []


# Global ClickHouse client instance
clickhouse_client = ClickHouseClient()
