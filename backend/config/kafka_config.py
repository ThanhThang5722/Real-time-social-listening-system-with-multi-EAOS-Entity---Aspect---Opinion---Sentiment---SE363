"""Kafka configuration settings"""
from typing import List

class KafkaConfig:
    """Kafka broker and topic configuration"""

    # Kafka broker settings
    BOOTSTRAP_SERVERS: List[str] = ["localhost:9092"]

    # Topic names
    COMMENTS_TOPIC = "eaos-comments"
    ANALYTICS_TOPIC = "eaos-analytics"

    # Producer settings
    PRODUCER_CONFIG = {
        "bootstrap_servers": BOOTSTRAP_SERVERS,
        "value_serializer": lambda v: v.encode('utf-8'),
        "acks": "all",  # Wait for all replicas to acknowledge
        "retries": 3,
        "max_in_flight_requests_per_connection": 1,
    }

    # Consumer settings
    CONSUMER_CONFIG = {
        "bootstrap_servers": BOOTSTRAP_SERVERS,
        "value_deserializer": lambda v: v.decode('utf-8'),
        "auto_offset_reset": "latest",  # Start from latest message
        "enable_auto_commit": True,
        "group_id": "eaos-dashboard-group",
    }

    # Stream settings
    COMMENT_INTERVAL = 2.0  # seconds between comments
    ANALYTICS_INTERVAL = 5.0  # seconds between analytics updates
