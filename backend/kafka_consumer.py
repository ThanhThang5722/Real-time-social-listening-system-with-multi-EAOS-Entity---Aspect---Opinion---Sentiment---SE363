"""
Kafka Consumer - Receive data from Kafka and stream via WebSocket

Usage:
    # Standalone consumer (save to MongoDB)
    python kafka_consumer.py --topic tv-comments --save-to-mongo

    # Or use in FastAPI WebSocket endpoint
    from kafka_consumer import KafkaDataConsumer
"""

import json
import asyncio
from typing import Optional, Callable, Dict, Any
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KafkaDataConsumer:
    """Consumer to receive data from Kafka and process/stream it"""

    def __init__(
        self,
        topic: str = "tv-comments",
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "tv-analytics-consumer",
        auto_offset_reset: str = "earliest"
    ):
        self.topic = topic
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.consumer = None
        self.running = False

    async def start(self):
        """Initialize Kafka consumer"""
        try:
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                enable_auto_commit=True,
                auto_commit_interval_ms=1000
            )
            await self.consumer.start()
            self.running = True
            logger.info(
                f"✅ Kafka consumer started: {self.bootstrap_servers} "
                f"| Topic: {self.topic} | Group: {self.group_id}"
            )
        except KafkaError as e:
            logger.error(f"❌ Failed to start Kafka consumer: {e}")
            raise

    async def stop(self):
        """Stop Kafka consumer"""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("🛑 Kafka consumer stopped")

    async def consume(
        self,
        callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
        max_messages: Optional[int] = None
    ):
        """
        Consume messages from Kafka

        Args:
            callback: Function to call for each message (async or sync)
            max_messages: Maximum number of messages to consume (None = infinite)
        """
        if not self.running:
            raise RuntimeError("Consumer not started. Call start() first.")

        message_count = 0

        try:
            async for msg in self.consumer:
                try:
                    # Process message
                    data = msg.value
                    logger.debug(
                        f"Received message: topic={msg.topic} "
                        f"partition={msg.partition} offset={msg.offset}"
                    )

                    # Call callback if provided
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)

                    message_count += 1

                    # Check if reached max messages
                    if max_messages and message_count >= max_messages:
                        logger.info(f"✅ Reached max messages: {max_messages}")
                        break

                    if message_count % 100 == 0:
                        logger.info(f"Processed {message_count} messages...")

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    continue

        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            logger.info(f"Total messages processed: {message_count}")


class WebSocketKafkaStreamer:
    """Stream Kafka messages to WebSocket clients"""

    def __init__(
        self,
        topic: str = "tv-comments",
        bootstrap_servers: str = "localhost:9092"
    ):
        self.consumer = KafkaDataConsumer(
            topic=topic,
            bootstrap_servers=bootstrap_servers,
            group_id="tv-analytics-websocket",
            auto_offset_reset="latest"  # Only new messages for WebSocket
        )
        self.websocket_clients = set()

    async def start(self):
        """Start Kafka consumer"""
        await self.consumer.start()

    async def stop(self):
        """Stop Kafka consumer"""
        await self.consumer.stop()

    def register_client(self, websocket):
        """Register WebSocket client"""
        self.websocket_clients.add(websocket)
        logger.info(f"WebSocket client registered. Total: {len(self.websocket_clients)}")

    def unregister_client(self, websocket):
        """Unregister WebSocket client"""
        self.websocket_clients.discard(websocket)
        logger.info(f"WebSocket client unregistered. Total: {len(self.websocket_clients)}")

    async def broadcast_to_clients(self, message: Dict[str, Any]):
        """Broadcast message to all WebSocket clients"""
        if not self.websocket_clients:
            return

        # Send to all clients
        disconnected = set()
        for websocket in self.websocket_clients:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to WebSocket client: {e}")
                disconnected.add(websocket)

        # Remove disconnected clients
        for websocket in disconnected:
            self.unregister_client(websocket)

    async def stream_to_websockets(self):
        """Stream Kafka messages to all connected WebSocket clients"""
        await self.consumer.consume(callback=self.broadcast_to_clients)


# MongoDB integration for saving consumed data
class MongoKafkaConsumer(KafkaDataConsumer):
    """Kafka consumer that saves messages to MongoDB"""

    def __init__(
        self,
        mongo_client,
        database: str = "tv_analytics",
        collection: str = "training_data",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.mongo_client = mongo_client
        self.database = database
        self.collection = collection

    async def save_to_mongo(self, message: Dict[str, Any]):
        """Save message to MongoDB"""
        try:
            db = self.mongo_client[self.database]
            collection = db[self.collection]

            # Add metadata
            message['_consumed_at'] = asyncio.get_event_loop().time()

            # Insert to MongoDB
            await collection.insert_one(message)

        except Exception as e:
            logger.error(f"Failed to save to MongoDB: {e}", exc_info=True)

    async def consume_and_save(self, max_messages: Optional[int] = None):
        """Consume messages and save to MongoDB"""
        await self.consume(callback=self.save_to_mongo, max_messages=max_messages)


async def main():
    import argparse
    from motor.motor_asyncio import AsyncIOMotorClient

    parser = argparse.ArgumentParser(description="Kafka Consumer")
    parser.add_argument(
        "--topic",
        default="tv-comments",
        help="Kafka topic (default: tv-comments)"
    )
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        help="Kafka bootstrap servers (default: localhost:9092)"
    )
    parser.add_argument(
        "--group-id",
        default="tv-analytics-consumer",
        help="Consumer group ID"
    )
    parser.add_argument(
        "--save-to-mongo",
        action="store_true",
        help="Save messages to MongoDB"
    )
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://admin:admin123@localhost:27017",
        help="MongoDB connection URI"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        help="Maximum messages to consume (default: infinite)"
    )

    args = parser.parse_args()

    try:
        if args.save_to_mongo:
            # Use MongoDB consumer
            logger.info("Using MongoDB consumer")
            mongo_client = AsyncIOMotorClient(args.mongo_uri)

            consumer = MongoKafkaConsumer(
                mongo_client=mongo_client,
                topic=args.topic,
                bootstrap_servers=args.bootstrap_servers,
                group_id=args.group_id
            )

            await consumer.start()
            await consumer.consume_and_save(max_messages=args.max_messages)

        else:
            # Use basic consumer
            logger.info("Using basic consumer (print to console)")

            consumer = KafkaDataConsumer(
                topic=args.topic,
                bootstrap_servers=args.bootstrap_servers,
                group_id=args.group_id
            )

            # Print callback
            def print_message(msg):
                print(json.dumps(msg, ensure_ascii=False, indent=2))

            await consumer.start()
            await consumer.consume(callback=print_message, max_messages=args.max_messages)

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        if 'consumer' in locals():
            await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
