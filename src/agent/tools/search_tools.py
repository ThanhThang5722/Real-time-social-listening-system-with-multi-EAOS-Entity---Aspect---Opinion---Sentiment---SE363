"""Agent tools for searching and analyzing comments"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from langchain.tools import tool
import structlog

from src.storage.elasticsearch_client import elasticsearch_client
from src.storage.clickhouse_client import clickhouse_client
from src.agent.tools.schemas import (
    SearchCommentsInput,
    SearchCommentsOutput,
    CommentResult
)

logger = structlog.get_logger(__name__)


@tool
async def search_comments(
    query: str,
    time_range: Optional[str] = None,
    sentiment_filter: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search comments by text with optional filters.

    Full-text search through viewer comments to find specific topics,
    keywords, or issues. Useful for investigating specific concerns.

    Args:
        query: Search query text (keywords, phrases)
        time_range: Optional time filter - "5min", "15min", or "1hour"
        sentiment_filter: Optional sentiment - "positive", "negative", or "neutral"
        limit: Maximum results to return (1-100)

    Returns:
        Dictionary with:
        - comments: List of matching comments with:
          - text: Comment text
          - timestamp: When posted
          - sentiment: Sentiment label
          - engagement_score: Engagement metric
          - username: (optional) Username
        - query: Search query used
        - total_found: Total matching comments

    Example:
        >>> result = await search_comments(
        ...     query="âm thanh",
        ...     sentiment_filter="negative",
        ...     limit=10
        ... )
        >>> print(f"Found {result['total_found']} comments about 'âm thanh'")
    """
    try:
        logger.info(
            "Searching comments",
            query=query,
            time_range=time_range,
            sentiment=sentiment_filter,
            limit=limit
        )

        # Calculate time bounds
        start_time = None
        end_time = datetime.now()

        if time_range:
            time_map = {"5min": 5, "15min": 15, "1hour": 60}
            minutes = time_map.get(time_range, 60)
            start_time = end_time - timedelta(minutes=minutes)

        # Search using Elasticsearch (fast full-text)
        results = await elasticsearch_client.search_comments(
            query=query,
            sentiment=sentiment_filter,
            start_time=start_time,
            end_time=end_time,
            size=limit
        )

        # Format results
        comments = []
        for result in results:
            comments.append({
                "text": result['text'],
                "timestamp": result['timestamp'],
                "sentiment": result['sentiment'],
                "engagement_score": result.get('engagement', 0),
                "username": result.get('username')
            })

        return {
            "comments": comments,
            "query": query,
            "total_found": len(comments),
            "filters": {
                "time_range": time_range,
                "sentiment": sentiment_filter
            }
        }

    except Exception as e:
        logger.error("Failed to search comments", query=query, error=str(e))
        return {
            "comments": [],
            "query": query,
            "total_found": 0,
            "error": str(e)
        }


@tool
async def get_sample_comments(
    entity: Optional[str] = None,
    sentiment: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get sample recent comments with optional filters.

    Retrieve representative comments for analysis. Useful for understanding
    the actual viewer feedback without specific search terms.

    Args:
        entity: Optional entity filter (e.g., "contestant_1")
        sentiment: Optional sentiment filter - "positive", "negative", "neutral"
        limit: Number of samples (1-50)

    Returns:
        Dictionary with sample comments list

    Example:
        >>> result = await get_sample_comments(
        ...     sentiment="negative",
        ...     limit=5
        ... )
        >>> for comment in result['comments']:
        ...     print(comment['text'][:100])
    """
    try:
        logger.info(
            "Getting sample comments",
            entity=entity,
            sentiment=sentiment,
            limit=limit
        )

        # Get samples from Elasticsearch
        results = await elasticsearch_client.get_sample_comments(
            entity=entity,
            sentiment=sentiment,
            size=limit
        )

        comments = []
        for result in results:
            comments.append({
                "text": result['text'],
                "timestamp": result['timestamp'],
                "sentiment": result['sentiment'],
                "engagement_score": result.get('engagement', 0),
                "username": result.get('username'),
                "entities": result.get('entities', [])
            })

        return {
            "comments": comments,
            "count": len(comments),
            "filters": {
                "entity": entity,
                "sentiment": sentiment
            }
        }

    except Exception as e:
        logger.error("Failed to get sample comments", error=str(e))
        return {
            "comments": [],
            "count": 0,
            "error": str(e)
        }


@tool
async def analyze_comment_themes(
    time_range: str = "15min",
    min_mentions: int = 5
) -> Dict[str, Any]:
    """
    Analyze common themes and topics in recent comments.

    Identifies recurring themes and patterns in viewer feedback.
    Useful for understanding overall audience concerns or interests.

    Args:
        time_range: Time range - "5min", "15min", or "1hour"
        min_mentions: Minimum mentions to be considered significant

    Returns:
        Dictionary with themes analysis

    Example:
        >>> result = await analyze_comment_themes(time_range="15min")
        >>> for theme in result['themes']:
        ...     print(f"{theme['name']}: {theme['count']} mentions")
    """
    try:
        logger.info("Analyzing comment themes", time_range=time_range)

        time_map = {"5min": 5, "15min": 15, "1hour": 60}
        minutes = time_map.get(time_range, 15)

        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=minutes)

        # Get entity mentions from Elasticsearch
        entities = await elasticsearch_client.get_entity_mention_counts(
            start_time=start_time,
            end_time=end_time,
            size=20
        )

        # Filter by min mentions
        themes = [
            {
                "name": e['entity'],
                "count": e['count'],
                "avg_sentiment": round(e['avg_sentiment'], 3),
                "sentiment_label": (
                    "positive" if e['avg_sentiment'] > 0.2
                    else "negative" if e['avg_sentiment'] < -0.2
                    else "neutral"
                )
            }
            for e in entities
            if e['count'] >= min_mentions
        ]

        return {
            "themes": themes,
            "time_range": time_range,
            "total_themes": len(themes),
            "timestamp": datetime.now()
        }

    except Exception as e:
        logger.error("Failed to analyze themes", error=str(e))
        return {
            "themes": [],
            "total_themes": 0,
            "error": str(e)
        }
