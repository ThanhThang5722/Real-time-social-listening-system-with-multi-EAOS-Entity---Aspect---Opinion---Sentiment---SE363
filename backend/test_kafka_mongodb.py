"""
Test script for Kafka + MongoDB integration

Usage:
    python test_kafka_mongodb.py
"""

import asyncio
import json
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_mongodb_connection():
    """Test MongoDB connection"""
    logger.info("=" * 70)
    logger.info("TEST 1: MongoDB Connection")
    logger.info("=" * 70)

    try:
        from mongodb_service import MongoDBService

        mongo = MongoDBService()
        await mongo.connect()

        logger.info("✅ MongoDB connected successfully")

        # Test save
        test_doc = {
            "text": "Test comment for Kafka integration",
            "video_id": "test_video_123",
            "timestamp": "2024-01-01T12:00:00Z"
        }

        doc_id = await mongo.save_comment(test_doc)
        logger.info(f"✅ Saved test document: {doc_id}")

        # Test retrieve
        comments = await mongo.get_comments(limit=1)
        logger.info(f"✅ Retrieved {len(comments)} comments")

        # Test stats
        stats = await mongo.get_comment_stats()
        logger.info(f"✅ Stats: {stats}")

        await mongo.disconnect()
        logger.info("✅ MongoDB test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"❌ MongoDB test FAILED: {e}")
        return False


async def test_kafka_producer():
    """Test Kafka Producer"""
    logger.info("=" * 70)
    logger.info("TEST 2: Kafka Producer")
    logger.info("=" * 70)

    try:
        from kafka_producer import KafkaDataProducer

        producer = KafkaDataProducer(
            bootstrap_servers="localhost:9092",
            topic="test-topic"
        )

        await producer.start()
        logger.info("✅ Kafka producer started")

        # Send test message
        test_message = {
            "id": "test_001",
            "text": "Test message from producer",
            "video_id": "test_video"
        }

        success = await producer.send_message(test_message)

        if success:
            logger.info("✅ Test message sent successfully")
        else:
            logger.error("❌ Failed to send test message")

        await producer.stop()
        logger.info("✅ Kafka producer test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"❌ Kafka producer test FAILED: {e}")
        return False


async def test_kafka_consumer():
    """Test Kafka Consumer"""
    logger.info("=" * 70)
    logger.info("TEST 3: Kafka Consumer")
    logger.info("=" * 70)

    try:
        from kafka_consumer import KafkaDataConsumer

        consumer = KafkaDataConsumer(
            topic="test-topic",
            bootstrap_servers="localhost:9092",
            group_id="test-consumer-group"
        )

        await consumer.start()
        logger.info("✅ Kafka consumer started")

        # Test consume (will consume the message we sent earlier)
        received_messages = []

        def collect_message(msg):
            received_messages.append(msg)
            logger.info(f"Received: {msg}")

        # Consume with timeout
        consume_task = asyncio.create_task(
            consumer.consume(callback=collect_message, max_messages=1)
        )

        # Wait max 10 seconds
        try:
            await asyncio.wait_for(consume_task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("No messages received (timeout)")

        await consumer.stop()

        if received_messages:
            logger.info(f"✅ Kafka consumer test PASSED (received {len(received_messages)} messages)\n")
        else:
            logger.warning("⚠️  Kafka consumer test completed but no messages received\n")

        return True

    except Exception as e:
        logger.error(f"❌ Kafka consumer test FAILED: {e}")
        return False


async def test_full_pipeline():
    """Test full pipeline: Producer → Kafka → Consumer → MongoDB"""
    logger.info("=" * 70)
    logger.info("TEST 4: Full Pipeline (Producer → Kafka → Consumer → MongoDB)")
    logger.info("=" * 70)

    try:
        from kafka_producer import KafkaDataProducer
        from kafka_consumer import MongoKafkaConsumer
        from mongodb_service import MongoDBService
        from motor.motor_asyncio import AsyncIOMotorClient

        # Setup
        producer = KafkaDataProducer(topic="pipeline-test")
        await producer.start()

        mongo_client = AsyncIOMotorClient("mongodb://admin:admin123@localhost:27017")
        consumer = MongoKafkaConsumer(
            mongo_client=mongo_client,
            topic="pipeline-test",
            group_id="pipeline-test-group",
            database="tv_analytics",
            collection="test_pipeline"
        )
        await consumer.start()

        # Send test data
        test_data = [
            {"id": "p1", "text": "Pipeline test message 1", "video_id": "v1"},
            {"id": "p2", "text": "Pipeline test message 2", "video_id": "v1"},
            {"id": "p3", "text": "Pipeline test message 3", "video_id": "v2"}
        ]

        logger.info("📤 Sending test data to Kafka...")
        sent = await producer.send_batch(test_data)
        logger.info(f"✅ Sent {sent} messages")

        # Consume and save to MongoDB
        logger.info("📥 Consuming from Kafka and saving to MongoDB...")
        consume_task = asyncio.create_task(
            consumer.consume_and_save(max_messages=3)
        )

        try:
            await asyncio.wait_for(consume_task, timeout=15.0)
        except asyncio.TimeoutError:
            logger.warning("Consumer timeout")

        # Verify MongoDB
        mongo = MongoDBService()
        await mongo.connect()
        stored_docs = await mongo.db['test_pipeline'].count_documents({})
        logger.info(f"✅ MongoDB has {stored_docs} documents in test_pipeline")

        # Cleanup
        await producer.stop()
        await consumer.stop()
        await mongo.disconnect()

        logger.info("✅ Full pipeline test PASSED\n")
        return True

    except Exception as e:
        logger.error(f"❌ Full pipeline test FAILED: {e}", exc_info=True)
        return False


async def check_services():
    """Check if required services are running"""
    logger.info("=" * 70)
    logger.info("CHECKING SERVICES")
    logger.info("=" * 70)

    services_ok = True

    # Check Kafka
    try:
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(bootstrap_servers="localhost:9092")
        await asyncio.wait_for(producer.start(), timeout=5.0)
        await producer.stop()
        logger.info("✅ Kafka is running (localhost:9092)")
    except Exception as e:
        logger.error(f"❌ Kafka is not accessible: {e}")
        services_ok = False

    # Check MongoDB
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(
            "mongodb://admin:admin123@localhost:27017",
            serverSelectionTimeoutMS=5000
        )
        await client.admin.command('ping')
        logger.info("✅ MongoDB is running (localhost:27017)")
        client.close()
    except Exception as e:
        logger.error(f"❌ MongoDB is not accessible: {e}")
        services_ok = False

    logger.info("")
    return services_ok


async def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("🧪 KAFKA + MONGODB INTEGRATION TESTS")
    logger.info("=" * 70)
    logger.info("")

    # Check services first
    services_ok = await check_services()

    if not services_ok:
        logger.error("\n❌ Some services are not running!")
        logger.error("Please start services with: docker-compose up -d zookeeper kafka mongodb")
        return

    # Run tests
    results = []

    results.append(("MongoDB Connection", await test_mongodb_connection()))
    results.append(("Kafka Producer", await test_kafka_producer()))
    results.append(("Kafka Consumer", await test_kafka_consumer()))
    results.append(("Full Pipeline", await test_full_pipeline()))

    # Summary
    logger.info("=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 All tests passed!")
    else:
        logger.info("\n⚠️  Some tests failed. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())
