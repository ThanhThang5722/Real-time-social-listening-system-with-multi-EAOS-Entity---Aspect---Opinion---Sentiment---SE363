"""Kafka Consumer service to consume comments from Kafka topic"""
import json
import asyncio
from typing import Optional, AsyncIterator
from datetime import datetime
from aiokafka import AIOKafkaConsumer
from config.kafka_config import KafkaConfig
from models.schemas import Comment, EAOSLabel


class KafkaConsumerService:
    """Service to consume comments from Kafka and provide to WebSocket clients"""

    def __init__(self, group_id: str = None):
        self.group_id = group_id or KafkaConfig.CONSUMER_CONFIG['group_id']
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.is_running = False

    async def start(self):
        """Initialize and start the Kafka consumer"""
        try:
            self.consumer = AIOKafkaConsumer(
                KafkaConfig.COMMENTS_TOPIC,
                bootstrap_servers=KafkaConfig.BOOTSTRAP_SERVERS,
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                auto_offset_reset='latest',  # Start from latest messages
                enable_auto_commit=True,
                group_id=self.group_id
            )
            await self.consumer.start()
            self.is_running = True
            print(f"[Kafka Consumer] Connected to Kafka topic: {KafkaConfig.COMMENTS_TOPIC}")
            print(f"[Kafka Consumer] Consumer group: {self.group_id}")
        except Exception as e:
            print(f"[Kafka Consumer] Failed to start: {e}")
            raise

    async def stop(self):
        """Stop the Kafka consumer"""
        self.is_running = False
        if self.consumer:
            await self.consumer.stop()
            print("[Kafka Consumer] Stopped")

    def _parse_comment(self, message_value: dict) -> Comment:
        """Parse Kafka message to Comment model"""
        try:
            # Parse labels
            labels = [
                EAOSLabel(**label) for label in message_value.get('labels', [])
            ]

            # Parse timestamp
            timestamp_str = message_value.get('timestamp')
            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

            return Comment(
                id=message_value.get('id'),
                text=message_value.get('text', ''),
                labels=labels,
                timestamp=timestamp,
                username=message_value.get('username', 'unknown')
            )
        except Exception as e:
            print(f"[Kafka Consumer] Error parsing comment: {e}")
            raise

    async def consume_comments(self) -> AsyncIterator[Comment]:
        """
        Async generator to consume comments from Kafka

        Yields:
            Comment objects from Kafka messages
        """
        try:
            async for message in self.consumer:
                try:
                    # Parse the message value to Comment model
                    comment = self._parse_comment(message.value)

                    print(f"[Kafka Consumer] Received comment: {comment.id}")
                    yield comment

                except Exception as e:
                    print(f"[Kafka Consumer] Error processing message: {e}")
                    continue

        except asyncio.CancelledError:
            print("[Kafka Consumer] Consumer cancelled")
            raise
        except Exception as e:
            print(f"[Kafka Consumer] Error in consume loop: {e}")
            raise

    async def get_latest_comment(self, timeout: float = 10.0) -> Optional[Comment]:
        """
        Get a single latest comment from Kafka

        Args:
            timeout: Maximum time to wait for a message in seconds

        Returns:
            Comment object or None if timeout
        """
        try:
            message = await asyncio.wait_for(
                self.consumer.__anext__(),
                timeout=timeout
            )
            return self._parse_comment(message.value)
        except asyncio.TimeoutError:
            print("[Kafka Consumer] Timeout waiting for message")
            return None
        except Exception as e:
            print(f"[Kafka Consumer] Error getting latest comment: {e}")
            return None
