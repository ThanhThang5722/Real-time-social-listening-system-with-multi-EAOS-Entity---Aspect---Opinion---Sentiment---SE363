"""Elasticsearch client for full-text search and topic analysis"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from elasticsearch import AsyncElasticsearch
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


class ElasticsearchClient:
    """Async Elasticsearch client for comment search and topic indexing"""

    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
        self.comments_index = settings.elasticsearch_index_comments
        self.trends_index = settings.elasticsearch_index_trends

    async def connect(self):
        """Initialize Elasticsearch connection"""
        try:
            self.client = AsyncElasticsearch(
                [settings.elasticsearch_url],
                verify_certs=False,
                request_timeout=30
            )
            # Test connection
            info = await self.client.info()
            logger.info(
                "Elasticsearch connected successfully",
                cluster=info['cluster_name'],
                version=info['version']['number']
            )
            await self._create_indices()
        except Exception as e:
            logger.error("Failed to connect to Elasticsearch", error=str(e))
            raise

    async def disconnect(self):
        """Close Elasticsearch connection"""
        if self.client:
            await self.client.close()
            logger.info("Elasticsearch disconnected")

    async def _create_indices(self):
        """Create indices with mappings if they don't exist"""
        try:
            # Comments index mapping
            comments_mapping = {
                "mappings": {
                    "properties": {
                        "comment_id": {"type": "keyword"},
                        "text": {
                            "type": "text",
                            "analyzer": "standard",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "username": {"type": "keyword"},
                        "timestamp": {"type": "date"},
                        "sentiment": {"type": "keyword"},
                        "sentiment_score": {"type": "float"},
                        "entities": {"type": "keyword"},
                        "topics": {"type": "keyword"},
                        "engagement": {"type": "integer"},
                        "metadata": {"type": "object", "enabled": False}
                    }
                }
            }

            if not await self.client.indices.exists(index=self.comments_index):
                await self.client.indices.create(
                    index=self.comments_index,
                    body=comments_mapping
                )
                logger.info("Comments index created", index=self.comments_index)

            # Trends index mapping
            trends_mapping = {
                "mappings": {
                    "properties": {
                        "topic": {"type": "keyword"},
                        "timestamp": {"type": "date"},
                        "mention_count": {"type": "integer"},
                        "time_window": {"type": "integer"},
                        "related_entities": {"type": "keyword"},
                        "sentiment_distribution": {"type": "object"}
                    }
                }
            }

            if not await self.client.indices.exists(index=self.trends_index):
                await self.client.indices.create(
                    index=self.trends_index,
                    body=trends_mapping
                )
                logger.info("Trends index created", index=self.trends_index)

        except Exception as e:
            logger.error("Failed to create indices", error=str(e))

    # ----------------------------------------
    # Comment Operations
    # ----------------------------------------

    async def index_comment(
        self,
        comment_id: str,
        text: str,
        username: str,
        timestamp: datetime,
        sentiment: str,
        sentiment_score: float,
        entities: List[str],
        topics: Optional[List[str]] = None,
        engagement: int = 0,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Index a comment for full-text search

        Args:
            comment_id: Unique comment identifier
            text: Comment text
            username: Username
            timestamp: Comment timestamp
            sentiment: Sentiment label
            sentiment_score: Sentiment score
            entities: Extracted entities
            topics: Extracted topics/keywords
            engagement: Engagement metric (likes, reactions)
            metadata: Additional metadata
        """
        try:
            document = {
                "comment_id": comment_id,
                "text": text,
                "username": username,
                "timestamp": timestamp,
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "entities": entities,
                "topics": topics or [],
                "engagement": engagement,
                "metadata": metadata or {}
            }

            await self.client.index(
                index=self.comments_index,
                id=comment_id,
                document=document
            )
            logger.debug("Comment indexed", comment_id=comment_id)
            return True
        except Exception as e:
            logger.error("Failed to index comment", comment_id=comment_id, error=str(e))
            return False

    async def bulk_index_comments(self, comments: List[Dict]) -> bool:
        """Bulk index multiple comments"""
        try:
            operations = []
            for comment in comments:
                operations.append({
                    "index": {
                        "_index": self.comments_index,
                        "_id": comment["comment_id"]
                    }
                })
                operations.append({
                    "comment_id": comment["comment_id"],
                    "text": comment["text"],
                    "username": comment["username"],
                    "timestamp": comment["timestamp"],
                    "sentiment": comment["sentiment"],
                    "sentiment_score": comment["sentiment_score"],
                    "entities": comment.get("entities", []),
                    "topics": comment.get("topics", []),
                    "engagement": comment.get("engagement", 0),
                    "metadata": comment.get("metadata", {})
                })

            response = await self.client.bulk(operations=operations)
            if response['errors']:
                logger.warning("Some comments failed to index")
            else:
                logger.info("Bulk comments indexed", count=len(comments))
            return not response['errors']
        except Exception as e:
            logger.error("Failed to bulk index comments", error=str(e))
            return False

    # ----------------------------------------
    # Search Operations
    # ----------------------------------------

    async def search_comments(
        self,
        query: str,
        sentiment: Optional[str] = None,
        entities: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        size: int = 100
    ) -> List[Dict]:
        """
        Full-text search comments with filters

        Args:
            query: Search query text
            sentiment: Filter by sentiment
            entities: Filter by entities
            start_time: Filter by start time
            end_time: Filter by end time
            size: Max results to return
        """
        try:
            must_clauses = []

            # Text search
            if query:
                must_clauses.append({
                    "match": {
                        "text": {
                            "query": query,
                            "operator": "or"
                        }
                    }
                })

            # Filters
            filter_clauses = []

            if sentiment:
                filter_clauses.append({"term": {"sentiment": sentiment}})

            if entities:
                filter_clauses.append({"terms": {"entities": entities}})

            if start_time or end_time:
                range_filter = {"range": {"timestamp": {}}}
                if start_time:
                    range_filter["range"]["timestamp"]["gte"] = start_time
                if end_time:
                    range_filter["range"]["timestamp"]["lte"] = end_time
                filter_clauses.append(range_filter)

            search_body = {
                "query": {
                    "bool": {
                        "must": must_clauses if must_clauses else [{"match_all": {}}],
                        "filter": filter_clauses
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}],
                "size": size
            }

            response = await self.client.search(
                index=self.comments_index,
                body=search_body
            )

            return [
                {
                    **hit["_source"],
                    "score": hit["_score"]
                }
                for hit in response["hits"]["hits"]
            ]
        except Exception as e:
            logger.error("Failed to search comments", query=query, error=str(e))
            return []

    async def get_sample_comments(
        self,
        entity: Optional[str] = None,
        sentiment: Optional[str] = None,
        size: int = 10
    ) -> List[Dict]:
        """Get sample comments for analysis"""
        try:
            filter_clauses = []

            if entity:
                filter_clauses.append({"term": {"entities": entity}})

            if sentiment:
                filter_clauses.append({"term": {"sentiment": sentiment}})

            search_body = {
                "query": {
                    "bool": {
                        "filter": filter_clauses if filter_clauses else [{"match_all": {}}]
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}],
                "size": size
            }

            response = await self.client.search(
                index=self.comments_index,
                body=search_body
            )

            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error("Failed to get sample comments", error=str(e))
            return []

    # ----------------------------------------
    # Topic/Trend Operations
    # ----------------------------------------

    async def index_trend(
        self,
        topic: str,
        timestamp: datetime,
        mention_count: int,
        time_window: int,
        related_entities: Optional[List[str]] = None,
        sentiment_distribution: Optional[Dict] = None
    ) -> bool:
        """Index a trending topic"""
        try:
            document = {
                "topic": topic,
                "timestamp": timestamp,
                "mention_count": mention_count,
                "time_window": time_window,
                "related_entities": related_entities or [],
                "sentiment_distribution": sentiment_distribution or {}
            }

            await self.client.index(
                index=self.trends_index,
                document=document
            )
            logger.debug("Trend indexed", topic=topic, mentions=mention_count)
            return True
        except Exception as e:
            logger.error("Failed to index trend", topic=topic, error=str(e))
            return False

    async def search_topics(
        self,
        query: str,
        time_window: Optional[int] = None,
        min_mentions: int = 0,
        size: int = 20
    ) -> List[Dict]:
        """Search trending topics"""
        try:
            filter_clauses = []

            if time_window:
                filter_clauses.append({"term": {"time_window": time_window}})

            if min_mentions > 0:
                filter_clauses.append({
                    "range": {"mention_count": {"gte": min_mentions}}
                })

            search_body = {
                "query": {
                    "bool": {
                        "must": [{"match": {"topic": query}}] if query else [{"match_all": {}}],
                        "filter": filter_clauses
                    }
                },
                "sort": [{"mention_count": {"order": "desc"}}],
                "size": size
            }

            response = await self.client.search(
                index=self.trends_index,
                body=search_body
            )

            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error("Failed to search topics", query=query, error=str(e))
            return []

    # ----------------------------------------
    # Aggregations
    # ----------------------------------------

    async def get_entity_mention_counts(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        size: int = 10
    ) -> List[Dict]:
        """Get entity mention counts with aggregation"""
        try:
            filter_clauses = []
            if start_time or end_time:
                range_filter = {"range": {"timestamp": {}}}
                if start_time:
                    range_filter["range"]["timestamp"]["gte"] = start_time
                if end_time:
                    range_filter["range"]["timestamp"]["lte"] = end_time
                filter_clauses.append(range_filter)

            search_body = {
                "size": 0,
                "query": {
                    "bool": {
                        "filter": filter_clauses if filter_clauses else [{"match_all": {}}]
                    }
                },
                "aggs": {
                    "entities": {
                        "terms": {
                            "field": "entities",
                            "size": size
                        },
                        "aggs": {
                            "avg_sentiment": {
                                "avg": {"field": "sentiment_score"}
                            }
                        }
                    }
                }
            }

            response = await self.client.search(
                index=self.comments_index,
                body=search_body
            )

            buckets = response["aggregations"]["entities"]["buckets"]
            return [
                {
                    "entity": bucket["key"],
                    "count": bucket["doc_count"],
                    "avg_sentiment": bucket["avg_sentiment"]["value"]
                }
                for bucket in buckets
            ]
        except Exception as e:
            logger.error("Failed to get entity counts", error=str(e))
            return []


# Global Elasticsearch client instance
elasticsearch_client = ElasticsearchClient()
