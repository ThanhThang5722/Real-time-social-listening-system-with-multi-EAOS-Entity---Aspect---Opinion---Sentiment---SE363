"""
MongoDB Service - Store and retrieve training data from Kafka

Usage:
    from mongodb_service import MongoDBService

    # Initialize
    mongo = MongoDBService()
    await mongo.connect()

    # Save training data
    await mongo.save_comment(comment_data)

    # Get training data
    data = await mongo.get_training_data(limit=1000)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MongoDBService:
    """Service for MongoDB operations"""

    def __init__(
        self,
        uri: str = "mongodb://admin:admin123@localhost:27017",
        database: str = "tv_analytics"
    ):
        self.uri = uri
        self.database_name = database
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.database_name]

            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"✅ Connected to MongoDB: {self.database_name}")

            # Create indexes
            await self._create_indexes()

        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("🛑 Disconnected from MongoDB")

    async def _create_indexes(self):
        """Create database indexes for performance"""
        try:
            # Training data collection
            training_data = self.db['training_data']
            await training_data.create_index([("consumed_at", DESCENDING)])
            await training_data.create_index([("video_id", ASCENDING)])
            await training_data.create_index([("created_at", DESCENDING)])

            # Comments collection
            comments = self.db['comments']
            await comments.create_index([("comment_id", ASCENDING)], unique=True)
            await comments.create_index([("video_id", ASCENDING)])
            await comments.create_index([("timestamp", DESCENDING)])

            logger.info("✅ Database indexes created")

        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")

    # ========================================================================
    # Training Data Operations
    # ========================================================================

    async def save_training_data(self, data: Dict[str, Any]) -> str:
        """
        Save training data from Kafka to MongoDB

        Args:
            data: Comment data with EAOS labels

        Returns:
            Inserted document ID
        """
        collection = self.db['training_data']

        # Add metadata
        document = {
            **data,
            "consumed_at": datetime.utcnow(),
            "is_used_for_training": False
        }

        result = await collection.insert_one(document)
        logger.debug(f"Saved training data: {result.inserted_id}")

        return str(result.inserted_id)

    async def get_training_data(
        self,
        limit: int = 1000,
        skip: int = 0,
        unused_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get training data for model training

        Args:
            limit: Maximum number of documents
            skip: Number of documents to skip
            unused_only: Only get data not yet used for training

        Returns:
            List of training data documents
        """
        collection = self.db['training_data']

        query = {}
        if unused_only:
            query["is_used_for_training"] = False

        cursor = collection.find(query).sort("consumed_at", DESCENDING).skip(skip).limit(limit)
        data = await cursor.to_list(length=limit)

        return data

    async def mark_as_used(self, document_ids: List[str]):
        """
        Mark training data as used

        Args:
            document_ids: List of document IDs to mark as used
        """
        from bson import ObjectId

        collection = self.db['training_data']

        object_ids = [ObjectId(id) for id in document_ids]

        result = await collection.update_many(
            {"_id": {"$in": object_ids}},
            {"$set": {"is_used_for_training": True, "used_at": datetime.utcnow()}}
        )

        logger.info(f"Marked {result.modified_count} documents as used")

    async def get_training_stats(self) -> Dict[str, Any]:
        """Get statistics about training data"""
        collection = self.db['training_data']

        total = await collection.count_documents({})
        used = await collection.count_documents({"is_used_for_training": True})
        unused = total - used

        return {
            "total": total,
            "used": used,
            "unused": unused,
            "usage_rate": (used / total * 100) if total > 0 else 0
        }

    # ========================================================================
    # Comment Operations
    # ========================================================================

    async def save_comment(self, comment: Dict[str, Any]) -> str:
        """
        Save comment from Kafka

        Args:
            comment: Comment data

        Returns:
            Inserted document ID or existing ID
        """
        collection = self.db['comments']

        # Check if comment already exists
        comment_id = comment.get('comment_id') or comment.get('id')
        if comment_id:
            existing = await collection.find_one({"comment_id": comment_id})
            if existing:
                logger.debug(f"Comment already exists: {comment_id}")
                return str(existing['_id'])

        # Add metadata
        document = {
            **comment,
            "stored_at": datetime.utcnow()
        }

        result = await collection.insert_one(document)
        logger.debug(f"Saved comment: {result.inserted_id}")

        return str(result.inserted_id)

    async def get_comments(
        self,
        video_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get comments from database

        Args:
            video_id: Filter by video ID (optional)
            limit: Maximum number of comments
            skip: Number of comments to skip

        Returns:
            List of comments
        """
        collection = self.db['comments']

        query = {}
        if video_id:
            query["video_id"] = video_id

        cursor = collection.find(query).sort("timestamp", DESCENDING).skip(skip).limit(limit)
        comments = await cursor.to_list(length=limit)

        return comments

    async def get_comment_stats(self) -> Dict[str, Any]:
        """Get statistics about comments"""
        collection = self.db['comments']

        total = await collection.count_documents({})

        # Count by video
        pipeline = [
            {"$group": {"_id": "$video_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        top_videos = await collection.aggregate(pipeline).to_list(length=10)

        return {
            "total_comments": total,
            "top_videos": top_videos
        }

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    async def bulk_insert_training_data(self, data_list: List[Dict[str, Any]]) -> int:
        """
        Bulk insert training data

        Args:
            data_list: List of training data documents

        Returns:
            Number of inserted documents
        """
        if not data_list:
            return 0

        collection = self.db['training_data']

        # Add metadata to all documents
        documents = [
            {
                **data,
                "consumed_at": datetime.utcnow(),
                "is_used_for_training": False
            }
            for data in data_list
        ]

        result = await collection.insert_many(documents)
        logger.info(f"Bulk inserted {len(result.inserted_ids)} training data documents")

        return len(result.inserted_ids)

    # ========================================================================
    # Export for Training
    # ========================================================================

    async def export_training_data(
        self,
        output_path: str,
        limit: int = 10000,
        unused_only: bool = True
    ):
        """
        Export training data to JSON file

        Args:
            output_path: Output file path
            limit: Maximum number of documents
            unused_only: Only export unused data
        """
        import json
        from pathlib import Path

        data = await self.get_training_data(limit=limit, unused_only=unused_only)

        # Remove MongoDB _id field
        for item in data:
            if '_id' in item:
                item['_id'] = str(item['_id'])

        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"✅ Exported {len(data)} documents to {output_path}")


# Singleton instance
_mongo_service: Optional[MongoDBService] = None


async def get_mongo_service() -> MongoDBService:
    """Get MongoDB service singleton instance"""
    global _mongo_service

    if _mongo_service is None:
        _mongo_service = MongoDBService()
        await _mongo_service.connect()

    return _mongo_service
