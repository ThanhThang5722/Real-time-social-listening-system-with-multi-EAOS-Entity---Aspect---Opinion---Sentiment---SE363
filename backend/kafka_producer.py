"""
Kafka Producer - Load data from files and send to Kafka

Usage:
    python kafka_producer.py --input data/comments.json --topic tv-comments
"""

import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KafkaDataProducer:
    """Producer to send data from files to Kafka"""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "tv-comments"
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None

    async def start(self):
        """Initialize Kafka producer"""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                compression_type='gzip',
                acks='all'
                #retries=3
            )
            await self.producer.start()
            logger.info(f"✅ Kafka producer started: {self.bootstrap_servers}")
        except KafkaError as e:
            logger.error(f"❌ Failed to start Kafka producer: {e}")
            raise

    async def stop(self):
        """Stop Kafka producer"""
        if self.producer:
            await self.producer.stop()
            logger.info("🛑 Kafka producer stopped")

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send single message to Kafka"""
        try:
            metadata = await self.producer.send_and_wait(
                self.topic,
                value=message
            )
            logger.debug(
                f"Message sent to {metadata.topic} "
                f"partition {metadata.partition} "
                f"offset {metadata.offset}"
            )
            return True
        except KafkaError as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_batch(self, messages: List[Dict[str, Any]]) -> int:
        """Send batch of messages to Kafka"""
        success_count = 0

        for idx, message in enumerate(messages, 1):
            if await self.send_message(message):
                success_count += 1

            if idx % 100 == 0:
                logger.info(f"Processed {idx}/{len(messages)} messages...")

        return success_count

    async def load_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """Load data from JSON file"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle both single object and array
        if isinstance(data, list):
            return data
        else:
            return [data]

    async def produce_from_file(
        self,
        input_path: str,
        batch_size: int = 1000
    ) -> int:
        """
        Load data from file and send to Kafka

        Args:
            input_path: Path to input file (JSON/JSONL)
            batch_size: Number of messages to send in batch

        Returns:
            Number of messages sent successfully
        """
        logger.info(f"📂 Loading data from: {input_path}")

        # Load data
        if input_path.endswith('.jsonl'):
            messages = []
            with open(input_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        messages.append(json.loads(line))
        else:
            messages = await self.load_from_json(input_path)

        logger.info(f"📊 Loaded {len(messages)} messages")

        # Send to Kafka
        logger.info(f"🚀 Sending to Kafka topic: {self.topic}")
        success_count = await self.send_batch(messages)

        logger.info(
            f"✅ Sent {success_count}/{len(messages)} messages successfully "
            f"({success_count/len(messages)*100:.1f}%)"
        )

        return success_count


async def main():
    parser = argparse.ArgumentParser(description="Kafka Producer - Load data from files")
    parser.add_argument(
        "--input",
        required=True,
        help="Input file path (JSON/JSONL)"
    )
    parser.add_argument(
        "--topic",
        default="tv-comments",
        help="Kafka topic name (default: tv-comments)"
    )
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        help="Kafka bootstrap servers (default: localhost:9092)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for sending messages (default: 1000)"
    )

    args = parser.parse_args()

    # Create producer
    producer = KafkaDataProducer(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic
    )

    try:
        # Start producer
        await producer.start()

        # Produce messages
        await producer.produce_from_file(
            input_path=args.input,
            batch_size=args.batch_size
        )

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
