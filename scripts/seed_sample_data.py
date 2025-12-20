"""Seed sample data for testing - uses V2 storage clients"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import asyncio
from datetime import datetime, timedelta
import random
from src.storage.redis_client_v2 import redis_client_v2
from src.storage.clickhouse_client_v2 import clickhouse_client_v2
from src.storage.elasticsearch_client_v2 import elasticsearch_client_v2
from src.config import settings
import structlog

logger = structlog.get_logger(__name__)


# Mapping Vietnamese sentiments to English
SENTIMENT_MAP = {
    "tích cực": "positive",
    "tiêu cực": "negative",
    "trung lập": "neutral"
}

SENTIMENT_SCORES = {
    "positive": 0.7,
    "negative": -0.6,
    "neutral": 0.0
}


def load_filtered_json():
    """Load comments from filtered.json"""
    json_path = Path(__file__).parent.parent.parent / "clean" / "filtered.json"

    if not json_path.exists():
        logger.warning(f"filtered.json not found at {json_path}")
        return []

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('results', [])


def extract_entities(labels):
    """Extract unique entities from labels"""
    entities = set()
    for label in labels:
        if label.get('entity'):
            entities.add(label['entity'])
    return list(entities)


def determine_sentiment(labels):
    """Determine overall sentiment from labels"""
    sentiments = [label.get('sentiment', 'trung lập') for label in labels]

    # Count sentiments
    positive = sentiments.count('tích cực')
    negative = sentiments.count('tiêu cực')

    if positive > negative:
        return "positive", SENTIMENT_SCORES["positive"]
    elif negative > positive:
        return "negative", SENTIMENT_SCORES["negative"]
    else:
        return "neutral", SENTIMENT_SCORES["neutral"]


async def seed_data(num_comments: int = 100, program_id: str = "show_123"):
    """Seed sample data into all databases using V2 clients"""
    logger.info(f"Starting to seed {num_comments} comments for program {program_id}...")

    # Connect to databases
    await redis_client_v2.connect()
    clickhouse_client_v2.connect()
    await elasticsearch_client_v2.connect()

    # Load source data
    source_comments = load_filtered_json()
    if not source_comments:
        logger.warning("No filtered.json found, generating mock data...")
        source_comments = [
            {
                "text": f"Sample comment {i}",
                "labels": [
                    {"entity": "show", "aspect": "content", "opinion": "good", "sentiment": "tích cực"}
                ]
            }
            for i in range(20)
        ]

    logger.info(f"Loaded {len(source_comments)} comments from source")

    # Generate timestamps (last hour with some data points)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)

    usernames = [f"user{i:03d}" for i in range(1, 51)]

    # Prepare data
    comments_to_insert = []
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    topic_mentions = {}

    for i in range(num_comments):
        # Select random source comment
        source = random.choice(source_comments)

        # Generate timestamp
        timestamp = start_time + timedelta(
            seconds=random.randint(0, 3600)
        )

        # Extract data
        topics = extract_entities(source['labels'])
        if not topics:
            topics = ["general"]

        sentiment, sentiment_score = determine_sentiment(source['labels'])
        sentiment_counts[sentiment] += 1

        # Count topic mentions
        for topic in topics:
            topic_mentions[topic] = topic_mentions.get(topic, 0) + 1

        engagement_score = random.randint(5, 100)

        comment = {
            "comment_id": f"comment_{i+1:05d}",
            "program_id": program_id,
            "text": source['text'],
            "username": random.choice(usernames),
            "timestamp": timestamp,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score + random.uniform(-0.1, 0.1),
            "engagement_score": engagement_score,
            "topics": topics,
            "metadata": {
                "source": "seed_script"
            }
        }

        comments_to_insert.append(comment)

    # Insert into Elasticsearch
    logger.info("Inserting into Elasticsearch...")
    await elasticsearch_client_v2.bulk_index(comments_to_insert)

    # Insert into ClickHouse - raw comments table
    logger.info("Inserting raw comments into ClickHouse...")
    for comment in comments_to_insert:
        clickhouse_client_v2.insert_raw_comment(
            program_id=comment["program_id"],
            timestamp=comment["timestamp"],
            comment_id=comment["comment_id"],
            text=comment["text"],
            sentiment=comment["sentiment"],
            sentiment_score=comment["sentiment_score"],
            engagement_score=comment["engagement_score"],
            topics=comment["topics"]
        )

    # Calculate EAOS score for program
    logger.info("Calculating EAOS metrics...")

    total_comments = num_comments
    avg_sentiment = sum(c["sentiment_score"] for c in comments_to_insert) / total_comments
    avg_engagement = sum(c["engagement_score"] for c in comments_to_insert) / total_comments

    # EAOS formula: weighted average of sentiment and normalized engagement
    eaos_score = (
        settings.eaos_sentiment_weight * ((avg_sentiment + 1) / 2) +  # Normalize -1..1 to 0..1
        settings.eaos_engagement_weight * (avg_engagement / 100.0)
    )

    # Insert EAOS metrics into ClickHouse with 5-minute intervals
    logger.info("Inserting EAOS timeline into ClickHouse...")
    for minutes_ago in range(60, 0, -5):
        point_time = end_time - timedelta(minutes=minutes_ago)

        # Add some variation to make timeline interesting
        variation = random.uniform(-0.05, 0.05)
        point_score = max(0, min(1, eaos_score + variation))

        # Distribute sentiment counts with variation
        point_positive = int(sentiment_counts["positive"] * (minutes_ago / 60) + random.randint(-5, 5))
        point_negative = int(sentiment_counts["negative"] * (minutes_ago / 60) + random.randint(-3, 3))
        point_neutral = int(sentiment_counts["neutral"] * (minutes_ago / 60) + random.randint(-2, 2))
        point_total = max(1, point_positive + point_negative + point_neutral)

        clickhouse_client_v2.insert_eaos_metric(
            program_id=program_id,
            timestamp=point_time,
            score=point_score,
            positive_count=max(0, point_positive),
            negative_count=max(0, point_negative),
            neutral_count=max(0, point_neutral),
            total_comments=point_total
        )

    # Insert comment aggregates by topic
    logger.info("Inserting comment aggregates into ClickHouse...")
    for topic, count in topic_mentions.items():
        clickhouse_client_v2.insert_comment_aggregate(
            program_id=program_id,
            timestamp=end_time,
            topic=topic,
            count=count,
            avg_sentiment=avg_sentiment
        )

    # Cache current EAOS in Redis
    logger.info("Caching current EAOS in Redis...")
    await redis_client_v2.set_current_eaos(
        program_id=program_id,
        score=eaos_score,
        positive=sentiment_counts["positive"],
        negative=sentiment_counts["negative"],
        neutral=sentiment_counts["neutral"],
        total=total_comments
    )

    # Cache trending topics
    logger.info("Caching trending topics in Redis...")
    for time_range in ["5min", "15min", "1hour"]:
        for topic, count in sorted(
            topic_mentions.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]:
            # Add variation based on time range
            score_multiplier = {"5min": 0.8, "15min": 1.0, "1hour": 1.2}[time_range]
            await redis_client_v2.add_trending_topic(
                time_range=time_range,
                topic=topic,
                score=count * score_multiplier
            )

    # Add program events
    logger.info("Adding program events to Redis...")
    events = [
        {"time": end_time - timedelta(minutes=45), "type": "segment_start", "desc": "Opening segment"},
        {"time": end_time - timedelta(minutes=30), "type": "commercial_break", "desc": "Commercial break"},
        {"time": end_time - timedelta(minutes=15), "type": "segment_start", "desc": "Main segment"},
    ]

    for event in events:
        await redis_client_v2.add_program_event(
            program_id=program_id,
            event_time=event["time"],
            event_type=event["type"],
            description=event["desc"]
        )

    logger.info(f"✓ Successfully seeded {num_comments} comments for program '{program_id}'!")
    logger.info(f"  EAOS Score: {eaos_score:.3f}")
    logger.info(f"  Sentiment: Positive={sentiment_counts['positive']}, Negative={sentiment_counts['negative']}, Neutral={sentiment_counts['neutral']}")
    logger.info(f"  Topics found: {len(topic_mentions)}")
    logger.info(f"  Top 5 topics: {list(sorted(topic_mentions.items(), key=lambda x: x[1], reverse=True))[:5]}")

    # Cleanup
    await redis_client_v2.disconnect()
    clickhouse_client_v2.disconnect()
    await elasticsearch_client_v2.disconnect()


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Seed sample data for TV Analytics system")
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of comments to seed (default: 100)"
    )
    parser.add_argument(
        "--program-id",
        type=str,
        default="show_123",
        help="Program ID to seed data for (default: show_123)"
    )

    args = parser.parse_args()

    await seed_data(num_comments=args.count, program_id=args.program_id)


if __name__ == "__main__":
    # Setup logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )

    asyncio.run(main())
