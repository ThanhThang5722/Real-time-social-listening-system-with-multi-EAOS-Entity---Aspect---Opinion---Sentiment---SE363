"""Kafka Producer service to push comments from file to Kafka topic"""
import json
import asyncio
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import random
from aiokafka import AIOKafkaProducer
from config.kafka_config import KafkaConfig


class KafkaProducerService:
    """Service to read comments from file and produce to Kafka topic"""

    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.comments: List[dict] = []
        self.current_index = 0
        self.producer: Optional[AIOKafkaProducer] = None
        self.is_running = False
        self._load_data()

    def _load_data(self):
        """Load comments from filtered.json"""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.comments = data.get('results', [])
                print(f"[Kafka Producer] Loaded {len(self.comments)} comments from {self.data_path}")
        except Exception as e:
            print(f"[Kafka Producer] Error loading data: {e}")
            self.comments = []

    async def start(self):
        """Initialize and start the Kafka producer"""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=KafkaConfig.BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.producer.start()
            self.is_running = True
            print(f"[Kafka Producer] Connected to Kafka at {KafkaConfig.BOOTSTRAP_SERVERS}")
        except Exception as e:
            print(f"[Kafka Producer] Failed to start: {e}")
            raise

    async def stop(self):
        """Stop the Kafka producer"""
        self.is_running = False
        if self.producer:
            await self.producer.stop()
            print("[Kafka Producer] Stopped")

    def _prepare_comment(self, comment_data: dict) -> dict:
        """Prepare comment data for Kafka message"""
        # Generate mock username if not present
        usernames = ["user123", "viewer456", "fan789", "livestream_watcher", "comment_user"]

        return {
            "id": f"comment_{self.current_index}_{datetime.now().timestamp()}",
            "text": comment_data.get('text', ''),
            "labels": comment_data.get('labels', []),
            "timestamp": datetime.now().isoformat(),
            "username": random.choice(usernames)
        }

    async def produce_comment(self, comment: dict):
        """Send a single comment to Kafka topic"""
        try:
            await self.producer.send_and_wait(
                KafkaConfig.COMMENTS_TOPIC,
                value=comment
            )
            print(f"[Kafka Producer] Sent comment: {comment['id']}")
        except Exception as e:
            print(f"[Kafka Producer] Error sending comment: {e}")

    async def stream_to_kafka(self, interval: float = None):
        """
        Continuously stream comments from file to Kafka

        Args:
            interval: Time between messages in seconds (default from config)
        """
        if interval is None:
            interval = KafkaConfig.COMMENT_INTERVAL

        print(f"[Kafka Producer] Starting to stream comments (interval={interval}s)")

        while self.is_running:
            try:
                if not self.comments:
                    print("[Kafka Producer] No comments available, waiting...")
                    await asyncio.sleep(interval)
                    continue

                # Get next comment (循环)
                comment_data = self.comments[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.comments)

                # Prepare and send to Kafka
                comment = self._prepare_comment(comment_data)
                await self.produce_comment(comment)

                # Wait for next iteration
                await asyncio.sleep(interval)

            except Exception as e:
                print(f"[Kafka Producer] Error in streaming loop: {e}")
                await asyncio.sleep(1)

    async def run(self, interval: float = None):
        """Start the producer and begin streaming"""
        try:
            await self.start()
            await self.stream_to_kafka(interval)
        except KeyboardInterrupt:
            print("[Kafka Producer] Interrupted by user")
        finally:
            await self.stop()
