"""MongoDB repository for storing comments and training data"""
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from config.mongodb_config import MongoDBConfig
from models.schemas import Comment


class MongoDBRepository:
    """Repository for MongoDB operations on comments and training data"""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.comments_collection: Optional[AsyncIOMotorCollection] = None
        self.training_data_collection: Optional[AsyncIOMotorCollection] = None
        self.is_connected = False

    async def connect(self):
        """Connect to MongoDB and initialize collections"""
        try:
            connection_string = MongoDBConfig.get_connection_string()
            self.client = AsyncIOMotorClient(
                connection_string,
                **MongoDBConfig.MOTOR_CLIENT_CONFIG
            )

            # Test connection
            await self.client.admin.command('ping')

            # Get database
            self.db = self.client[MongoDBConfig.DATABASE_NAME]

            # Get collections
            self.comments_collection = self.db[MongoDBConfig.COMMENTS_COLLECTION]
            self.training_data_collection = self.db[MongoDBConfig.TRAINING_DATA_COLLECTION]

            # Create indexes
            await self._create_indexes()

            self.is_connected = True
            print(f"[MongoDB] Connected to database: {MongoDBConfig.DATABASE_NAME}")

        except ConnectionFailure as e:
            print(f"[MongoDB] Connection failed: {e}")
            raise
        except Exception as e:
            print(f"[MongoDB] Error during connection: {e}")
            raise

    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.is_connected = False
            print("[MongoDB] Disconnected")

    async def _create_indexes(self):
        """Create indexes for efficient querying"""
        try:
            # Index on comment ID (unique)
            await self.comments_collection.create_index("id", unique=True)

            # Index on timestamp for time-based queries
            await self.comments_collection.create_index("timestamp")

            # Index on sentiment for analytics
            await self.comments_collection.create_index("labels.sentiment")

            # Index on username
            await self.comments_collection.create_index("username")

            # Compound index for training data queries
            await self.training_data_collection.create_index([
                ("created_at", -1),
                ("is_processed", 1)
            ])

            print("[MongoDB] Indexes created successfully")

        except Exception as e:
            print(f"[MongoDB] Error creating indexes: {e}")

    def _comment_to_dict(self, comment: Comment) -> Dict[str, Any]:
        """Convert Comment model to MongoDB document"""
        return {
            "id": comment.id,
            "text": comment.text,
            "labels": [
                {
                    "entity": label.entity,
                    "aspect": label.aspect,
                    "opinion": label.opinion,
                    "sentiment": label.sentiment
                }
                for label in comment.labels
            ],
            "timestamp": comment.timestamp,
            "username": comment.username,
            "created_at": datetime.now(),
            "source": "kafka"  # Mark that this came from Kafka stream
        }

    async def save_comment(self, comment: Comment) -> bool:
        """
        Save a single comment to MongoDB

        Args:
            comment: Comment object to save

        Returns:
            True if saved successfully, False if duplicate or error
        """
        if not self.is_connected:
            print("[MongoDB] Not connected, skipping save")
            return False

        try:
            doc = self._comment_to_dict(comment)

            # Check for duplicates if enabled
            if MongoDBConfig.ENABLE_DUPLICATE_CHECK:
                existing = await self.comments_collection.find_one({"id": comment.id})
                if existing:
                    print(f"[MongoDB] Comment {comment.id} already exists, skipping")
                    return False

            await self.comments_collection.insert_one(doc)
            print(f"[MongoDB] Saved comment: {comment.id}")
            return True

        except DuplicateKeyError:
            print(f"[MongoDB] Duplicate comment ID: {comment.id}")
            return False
        except Exception as e:
            print(f"[MongoDB] Error saving comment: {e}")
            return False

    async def save_comments_batch(self, comments: List[Comment]) -> int:
        """
        Save multiple comments in batch

        Args:
            comments: List of Comment objects

        Returns:
            Number of successfully inserted documents
        """
        if not self.is_connected or not comments:
            return 0

        try:
            docs = [self._comment_to_dict(comment) for comment in comments]
            result = await self.comments_collection.insert_many(docs, ordered=False)
            inserted_count = len(result.inserted_ids)
            print(f"[MongoDB] Batch saved {inserted_count}/{len(comments)} comments")
            return inserted_count

        except Exception as e:
            print(f"[MongoDB] Error in batch save: {e}")
            return 0

    async def get_comments_count(self) -> int:
        """Get total number of comments in database"""
        if not self.is_connected:
            return 0
        return await self.comments_collection.count_documents({})

    async def get_recent_comments(self, limit: int = 100) -> List[Dict]:
        """
        Get recent comments

        Args:
            limit: Maximum number of comments to return

        Returns:
            List of comment documents
        """
        if not self.is_connected:
            return []

        cursor = self.comments_collection.find().sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_comments_by_sentiment(self, sentiment: str, limit: int = 100) -> List[Dict]:
        """
        Get comments filtered by sentiment

        Args:
            sentiment: Sentiment value (e.g., "tích cực", "tiêu cực", "trung lập")
            limit: Maximum number of results

        Returns:
            List of matching comments
        """
        if not self.is_connected:
            return []

        cursor = self.comments_collection.find(
            {"labels.sentiment": sentiment}
        ).limit(limit)

        return await cursor.to_list(length=limit)

    async def get_training_data(self, limit: int = 1000, skip: int = 0) -> List[Dict]:
        """
        Get comments for training purposes

        Args:
            limit: Maximum number of documents
            skip: Number of documents to skip

        Returns:
            List of comments formatted for training
        """
        if not self.is_connected:
            return []

        cursor = self.comments_collection.find(
            {},
            {"_id": 0, "text": 1, "labels": 1, "timestamp": 1}
        ).skip(skip).limit(limit)

        return await cursor.to_list(length=limit)

    async def export_training_data(self) -> Dict[str, Any]:
        """
        Export all data for model training

        Returns:
            Dictionary with training data statistics
        """
        if not self.is_connected:
            return {"error": "Not connected"}

        total_count = await self.get_comments_count()
        all_data = await self.get_training_data(limit=total_count)

        # Save to training_data collection with metadata
        training_export = {
            "exported_at": datetime.now(),
            "total_comments": total_count,
            "data": all_data,
            "is_processed": False
        }

        result = await self.training_data_collection.insert_one(training_export)

        print(f"[MongoDB] Exported {total_count} comments for training")

        return {
            "export_id": str(result.inserted_id),
            "total_comments": total_count,
            "exported_at": training_export["exported_at"]
        }

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics

        Returns:
            Dictionary with various statistics
        """
        if not self.is_connected:
            return {}

        total_comments = await self.get_comments_count()

        # Sentiment distribution
        pipeline = [
            {"$unwind": "$labels"},
            {"$group": {
                "_id": "$labels.sentiment",
                "count": {"$sum": 1}
            }}
        ]

        sentiment_dist = {}
        async for doc in self.comments_collection.aggregate(pipeline):
            sentiment_dist[doc["_id"]] = doc["count"]

        return {
            "total_comments": total_comments,
            "sentiment_distribution": sentiment_dist,
            "collections": {
                "comments": MongoDBConfig.COMMENTS_COLLECTION,
                "training_data": MongoDBConfig.TRAINING_DATA_COLLECTION
            }
        }


# Global instance (singleton pattern)
_mongodb_repository: Optional[MongoDBRepository] = None


async def get_mongodb_repository() -> MongoDBRepository:
    """Get or create MongoDB repository instance"""
    global _mongodb_repository

    if _mongodb_repository is None:
        _mongodb_repository = MongoDBRepository()
        await _mongodb_repository.connect()

    return _mongodb_repository
