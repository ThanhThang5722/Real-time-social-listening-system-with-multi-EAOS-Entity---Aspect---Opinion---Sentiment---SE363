"""Updated ClickHouse client matching new schema specifications"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import clickhouse_connect
from clickhouse_connect.driver import Client
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


class ClickHouseClientV2:
    """
    ClickHouse client for new schema:
    - eaos_metrics: program_id, timestamp, score, positive_count, negative_count, neutral_count, total_comments
    - comment_aggregates: program_id, timestamp, topic, count, avg_sentiment
    - anomalies: program_id, timestamp, metric, value, expected, deviation, severity
    - raw_comments: detailed comment storage
    """

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
    # EAOS Metrics Operations
    # ----------------------------------------

    def insert_eaos_metric(
        self,
        program_id: str,
        timestamp: datetime,
        score: float,
        positive_count: int,
        negative_count: int,
        neutral_count: int,
        total_comments: int
    ) -> bool:
        """Insert EAOS metric record"""
        try:
            self.client.insert(
                "eaos_metrics",
                [[program_id, timestamp, score, positive_count, negative_count, neutral_count, total_comments]],
                column_names=[
                    "program_id", "timestamp", "score",
                    "positive_count", "negative_count", "neutral_count", "total_comments"
                ]
            )
            logger.debug("EAOS metric inserted", program_id=program_id, score=score)
            return True
        except Exception as e:
            logger.error("Failed to insert EAOS metric", program_id=program_id, error=str(e))
            return False

    def get_eaos_timeline(
        self,
        program_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Get EAOS timeline for a program"""
        try:
            query = """
                SELECT
                    timestamp,
                    score,
                    positive_count,
                    negative_count,
                    neutral_count,
                    total_comments
                FROM eaos_metrics
                WHERE program_id = %(program_id)s
                    AND timestamp >= %(start_time)s
                    AND timestamp <= %(end_time)s
                ORDER BY timestamp ASC
            """

            result = self.client.query(
                query,
                parameters={
                    "program_id": program_id,
                    "start_time": start_time,
                    "end_time": end_time
                }
            )

            return [
                {
                    "timestamp": row[0],
                    "score": row[1],
                    "positive_count": row[2],
                    "negative_count": row[3],
                    "neutral_count": row[4],
                    "total_comments": row[5]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to get EAOS timeline", program_id=program_id, error=str(e))
            return []

    def get_latest_eaos(self, program_id: str) -> Optional[Dict]:
        """Get most recent EAOS metric"""
        try:
            query = """
                SELECT
                    timestamp,
                    score,
                    positive_count,
                    negative_count,
                    neutral_count,
                    total_comments
                FROM eaos_metrics
                WHERE program_id = %(program_id)s
                ORDER BY timestamp DESC
                LIMIT 1
            """

            result = self.client.query(query, parameters={"program_id": program_id})

            if not result.result_rows:
                return None

            row = result.result_rows[0]
            return {
                "timestamp": row[0],
                "score": row[1],
                "positive_count": row[2],
                "negative_count": row[3],
                "neutral_count": row[4],
                "total_comments": row[5]
            }
        except Exception as e:
            logger.error("Failed to get latest EAOS", program_id=program_id, error=str(e))
            return None

    # ----------------------------------------
    # Comment Aggregates Operations
    # ----------------------------------------

    def insert_comment_aggregate(
        self,
        program_id: str,
        timestamp: datetime,
        topic: str,
        count: int,
        avg_sentiment: float
    ) -> bool:
        """Insert comment aggregate record"""
        try:
            self.client.insert(
                "comment_aggregates",
                [[program_id, timestamp, topic, count, avg_sentiment]],
                column_names=["program_id", "timestamp", "topic", "count", "avg_sentiment"]
            )
            logger.debug("Comment aggregate inserted", program_id=program_id, topic=topic)
            return True
        except Exception as e:
            logger.error("Failed to insert comment aggregate", error=str(e))
            return False

    def get_top_topics(
        self,
        program_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[Dict]:
        """Get top topics for time range"""
        try:
            query = """
                SELECT
                    topic,
                    sum(count) as total_count,
                    avg(avg_sentiment) as avg_sentiment
                FROM comment_aggregates
                WHERE program_id = %(program_id)s
                    AND timestamp >= %(start_time)s
                    AND timestamp <= %(end_time)s
                GROUP BY topic
                ORDER BY total_count DESC
                LIMIT %(limit)s
            """

            result = self.client.query(
                query,
                parameters={
                    "program_id": program_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "limit": limit
                }
            )

            return [
                {
                    "topic": row[0],
                    "count": row[1],
                    "avg_sentiment": row[2]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to get top topics", program_id=program_id, error=str(e))
            return []

    # ----------------------------------------
    # Anomalies Operations
    # ----------------------------------------

    def insert_anomaly(
        self,
        program_id: str,
        timestamp: datetime,
        metric: str,
        value: float,
        expected: float,
        deviation: float,
        severity: str
    ) -> bool:
        """Insert anomaly record"""
        try:
            self.client.insert(
                "anomalies",
                [[program_id, timestamp, metric, value, expected, deviation, severity]],
                column_names=[
                    "program_id", "timestamp", "metric",
                    "value", "expected", "deviation", "severity"
                ]
            )
            logger.info(
                "Anomaly inserted",
                program_id=program_id,
                metric=metric,
                severity=severity
            )
            return True
        except Exception as e:
            logger.error("Failed to insert anomaly", error=str(e))
            return False

    def get_recent_anomalies(
        self,
        program_id: str,
        hours: int = 1,
        severity: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Get recent anomalies"""
        try:
            severity_filter = f"AND severity = '{severity}'" if severity else ""

            query = f"""
                SELECT
                    timestamp,
                    metric,
                    value,
                    expected,
                    deviation,
                    severity
                FROM anomalies
                WHERE program_id = %(program_id)s
                    AND timestamp >= now() - INTERVAL {hours} HOUR
                    {severity_filter}
                ORDER BY timestamp DESC
                LIMIT %(limit)s
            """

            result = self.client.query(
                query,
                parameters={"program_id": program_id, "limit": limit}
            )

            return [
                {
                    "timestamp": row[0],
                    "metric": row[1],
                    "value": row[2],
                    "expected": row[3],
                    "deviation": row[4],
                    "severity": row[5]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to get recent anomalies", program_id=program_id, error=str(e))
            return []

    # ----------------------------------------
    # Raw Comments Operations
    # ----------------------------------------

    def insert_raw_comment(
        self,
        comment_id: str,
        program_id: str,
        text: str,
        username: str,
        timestamp: datetime,
        sentiment: str,
        sentiment_score: float,
        engagement_score: int,
        topics: List[str],
        metadata: str = "{}"
    ) -> bool:
        """Insert raw comment"""
        try:
            self.client.insert(
                "raw_comments",
                [[
                    comment_id, program_id, text, username, timestamp,
                    sentiment, sentiment_score, engagement_score, topics, metadata
                ]],
                column_names=[
                    "comment_id", "program_id", "text", "username", "timestamp",
                    "sentiment", "sentiment_score", "engagement_score", "topics", "metadata"
                ]
            )
            logger.debug("Raw comment inserted", comment_id=comment_id)
            return True
        except Exception as e:
            logger.error("Failed to insert raw comment", error=str(e))
            return False

    def search_comments(
        self,
        program_id: str,
        query: Optional[str] = None,
        sentiment: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search raw comments"""
        try:
            conditions = [f"program_id = '{program_id}'"]

            if query:
                conditions.append(f"positionCaseInsensitive(text, '{query}') > 0")
            if sentiment:
                conditions.append(f"sentiment = '{sentiment}'")
            if start_time:
                conditions.append(f"timestamp >= '{start_time.isoformat()}'")
            if end_time:
                conditions.append(f"timestamp <= '{end_time.isoformat()}'")

            where_clause = " AND ".join(conditions)

            sql = f"""
                SELECT
                    comment_id,
                    text,
                    username,
                    timestamp,
                    sentiment,
                    sentiment_score,
                    engagement_score,
                    topics
                FROM raw_comments
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT {limit}
            """

            result = self.client.query(sql)

            return [
                {
                    "comment_id": row[0],
                    "text": row[1],
                    "username": row[2],
                    "timestamp": row[3],
                    "sentiment": row[4],
                    "sentiment_score": row[5],
                    "engagement_score": row[6],
                    "topics": row[7]
                }
                for row in result.result_rows
            ]
        except Exception as e:
            logger.error("Failed to search comments", program_id=program_id, error=str(e))
            return []


# Global instance
clickhouse_client_v2 = ClickHouseClientV2()
