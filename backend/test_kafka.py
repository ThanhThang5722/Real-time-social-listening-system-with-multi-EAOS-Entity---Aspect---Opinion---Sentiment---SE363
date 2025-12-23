"""
Test script for Kafka Producer and Consumer

Usage:
    python test_kafka.py producer   # Test producer only
    python test_kafka.py consumer   # Test consumer only
    python test_kafka.py both       # Test both (default)
"""
import asyncio
import sys
from pathlib import Path
from services.kafka_producer import KafkaProducerService
from services.kafka_consumer import KafkaConsumerService


async def test_producer(data_path: str, duration: int = 30):
    """Test Kafka Producer"""
    print("=" * 60)
    print("Testing Kafka Producer")
    print("=" * 60)

    producer = KafkaProducerService(data_path)

    try:
        await producer.start()
        print(f"\n✓ Producer started successfully")
        print(f"Streaming comments for {duration} seconds...")

        # Run producer for specified duration
        producer_task = asyncio.create_task(producer.stream_to_kafka(interval=1.0))

        await asyncio.sleep(duration)

        producer_task.cancel()
        try:
            await producer_task
        except asyncio.CancelledError:
            pass

        print(f"\n✓ Producer test completed")

    except Exception as e:
        print(f"\n✗ Producer error: {e}")
        raise
    finally:
        await producer.stop()


async def test_consumer(duration: int = 30):
    """Test Kafka Consumer"""
    print("=" * 60)
    print("Testing Kafka Consumer")
    print("=" * 60)

    consumer = KafkaConsumerService(group_id="test-consumer-group")

    try:
        await consumer.start()
        print(f"\n✓ Consumer started successfully")
        print(f"Consuming comments for {duration} seconds...")
        print("-" * 60)

        count = 0
        start_time = asyncio.get_event_loop().time()

        async for comment in consumer.consume_comments():
            count += 1
            print(f"\n[{count}] Comment ID: {comment.id}")
            print(f"    User: {comment.username}")
            print(f"    Text: {comment.text[:50]}...")
            print(f"    Labels: {len(comment.labels)} EAOS labels")
            print(f"    Sentiment: {comment.labels[0].sentiment if comment.labels else 'N/A'}")

            # Check if duration elapsed
            if asyncio.get_event_loop().time() - start_time > duration:
                break

        print("-" * 60)
        print(f"\n✓ Consumer test completed")
        print(f"Total messages received: {count}")

    except Exception as e:
        print(f"\n✗ Consumer error: {e}")
        raise
    finally:
        await consumer.stop()


async def test_both(data_path: str):
    """Test both Producer and Consumer together"""
    print("=" * 60)
    print("Testing Kafka Producer + Consumer Together")
    print("=" * 60)

    producer = KafkaProducerService(data_path)
    consumer = KafkaConsumerService(group_id="test-both-group")

    try:
        # Start producer
        await producer.start()
        producer_task = asyncio.create_task(producer.stream_to_kafka(interval=2.0))
        print("✓ Producer started")

        # Wait a bit for producer to send some messages
        await asyncio.sleep(3)

        # Start consumer
        await consumer.start()
        print("✓ Consumer started")
        print("-" * 60)

        # Consume for 30 seconds
        count = 0
        start_time = asyncio.get_event_loop().time()

        async for comment in consumer.consume_comments():
            count += 1
            print(f"[{count}] {comment.username}: {comment.text[:40]}... ({comment.labels[0].sentiment if comment.labels else 'N/A'})")

            if asyncio.get_event_loop().time() - start_time > 20:
                break

        print("-" * 60)
        print(f"\n✓ Test completed - Received {count} messages")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise
    finally:
        # Cleanup
        producer_task.cancel()
        try:
            await producer_task
        except asyncio.CancelledError:
            pass

        await producer.stop()
        await consumer.stop()
        print("✓ Cleanup completed")


async def main():
    # Determine test mode
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"

    # Path to data file
    data_path = Path(__file__).parent.parent.parent / "clean" / "filtered.json"

    if not data_path.exists():
        print(f"✗ Error: Data file not found at {data_path}")
        print("Please ensure filtered.json exists")
        return

    print(f"\nData path: {data_path}")
    print(f"Test mode: {mode}\n")

    try:
        if mode == "producer":
            await test_producer(str(data_path))
        elif mode == "consumer":
            await test_consumer()
        elif mode == "both":
            await test_both(str(data_path))
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python test_kafka.py [producer|consumer|both]")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Kafka Test Script")
    print("=" * 60)
    print("\nMake sure Kafka is running:")
    print("  docker-compose up -d")
    print("\nThen run this script:")
    print("  python test_kafka.py [producer|consumer|both]")
    print("=" * 60 + "\n")

    asyncio.run(main())
