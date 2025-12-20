"""Updated Elasticsearch client with new schema"""

from typing import List, Dict, Optional
from datetime import datetime
from elasticsearch import AsyncElasticsearch
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


class ElasticsearchClientV2:
    """
    Elasticsearch client with schema:
    - comments index: text, program_id, timestamp, sentiment, engagement_score, topics[]
    """

    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
        self.comments_index = settings.elasticsearch_index_comments

    async def connect(self):
        """Initialize Elasticsearch connection"""
        try:
            self.client = AsyncElasticsearch(
                [settings.elasticsearch_url],
                verify_certs=False,
                request_timeout=30
            )
            info = await self.client.info()
            logger.info(
                "Elasticsearch connected",
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
        """Create index with updated mapping"""
        try:
            # Updated comments mapping
            comments_mapping = {
                "mappings": {
                    "properties": {
                        "comment_id": {"type": "keyword"},
                        "program_id": {"type": "keyword"},
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
                        "engagement_score": {"type": "integer"},
                        "topics": {"type": "keyword"},  # Array of topics
                        "metadata": {"type": "object", "enabled": False}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "1s"
                }
            }

            if not await self.client.indices.exists(index=self.comments_index):
                await self.client.indices.create(
                    index=self.comments_index,
                    body=comments_mapping
                )
                logger.info("Comments index created", index=self.comments_index)
            else:
                logger.info("Comments index already exists", index=self.comments_index)

        except Exception as e:
            logger.error("Failed to create indices", error=str(e))

    # ----------------------------------------
    # Index Operations
    # ----------------------------------------

    async def index_comment(
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
        metadata: Optional[Dict] = None
    ) -> bool:
        """Index a comment"""
        try:
            document = {
                "comment_id": comment_id,
                "program_id": program_id,
                "text": text,
                "username": username,
                "timestamp": timestamp,
                "sentiment": sentiment,
                "sentiment_score": sentiment_score,
                "engagement_score": engagement_score,
                "topics": topics,
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
        """Bulk index comments"""
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
                    "program_id": comment["program_id"],
                    "text": comment["text"],
                    "username": comment["username"],
                    "timestamp": comment["timestamp"],
                    "sentiment": comment["sentiment"],
                    "sentiment_score": comment["sentiment_score"],
                    "engagement_score": comment.get("engagement_score", 0),
                    "topics": comment.get("topics", []),
                    "metadata": comment.get("metadata", {})
                })

            response = await self.client.bulk(operations=operations)
            if response['errors']:
                logger.warning("Some comments failed to index")
            else:
                logger.info("Bulk comments indexed", count=len(comments))
            return not response['errors']
        except Exception as e:
            logger.error("Failed to bulk index", error=str(e))
            return False

    # ----------------------------------------
    # Search Operations
    # ----------------------------------------

    async def search_comments(
        self,
        program_id: Optional[str] = None,
        query: Optional[str] = None,
        sentiment: Optional[str] = None,
        topics: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        size: int = 50
    ) -> List[Dict]:
        """Search comments with filters"""
        try:
            must_clauses = []
            filter_clauses = []

            # Program filter
            if program_id:
                filter_clauses.append({"term": {"program_id": program_id}})

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

            # Sentiment filter
            if sentiment:
                filter_clauses.append({"term": {"sentiment": sentiment}})

            # Topics filter
            if topics:
                filter_clauses.append({"terms": {"topics": topics}})

            # Time range filter
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
            logger.error("Failed to search comments", error=str(e))
            return []

    # ----------------------------------------
    # Aggregations
    # ----------------------------------------

    async def get_topic_distribution(
        self,
        program_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        size: int = 20
    ) -> List[Dict]:
        """Get topic distribution for a program"""
        try:
            filter_clauses = [{"term": {"program_id": program_id}}]

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
                        "filter": filter_clauses
                    }
                },
                "aggs": {
                    "topics": {
                        "terms": {
                            "field": "topics",
                            "size": size
                        },
                        "aggs": {
                            "avg_sentiment": {
                                "avg": {"field": "sentiment_score"}
                            },
                            "avg_engagement": {
                                "avg": {"field": "engagement_score"}
                            }
                        }
                    }
                }
            }

            response = await self.client.search(
                index=self.comments_index,
                body=search_body
            )

            buckets = response["aggregations"]["topics"]["buckets"]
            return [
                {
                    "topic": bucket["key"],
                    "count": bucket["doc_count"],
                    "avg_sentiment": bucket["avg_sentiment"]["value"],
                    "avg_engagement": bucket["avg_engagement"]["value"]
                }
                for bucket in buckets
            ]
        except Exception as e:
            logger.error("Failed to get topic distribution", error=str(e))
            return []

    async def get_sentiment_distribution(
        self,
        program_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Get sentiment distribution"""
        try:
            filter_clauses = [{"term": {"program_id": program_id}}]

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
                        "filter": filter_clauses
                    }
                },
                "aggs": {
                    "sentiments": {
                        "terms": {"field": "sentiment"}
                    }
                }
            }

            response = await self.client.search(
                index=self.comments_index,
                body=search_body
            )

            return {
                bucket["key"]: bucket["doc_count"]
                for bucket in response["aggregations"]["sentiments"]["buckets"]
            }
        except Exception as e:
            logger.error("Failed to get sentiment distribution", error=str(e))
            return {}


# Global instance
elasticsearch_client_v2 = ElasticsearchClientV2()
