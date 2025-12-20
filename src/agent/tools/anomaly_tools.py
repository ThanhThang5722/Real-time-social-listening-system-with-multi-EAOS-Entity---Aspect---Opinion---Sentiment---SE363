"""Agent tools for anomaly detection and program events"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from langchain.tools import tool
import structlog
import statistics

from src.storage.clickhouse_client import clickhouse_client
from src.storage.redis_client import redis_client
from src.agent.tools.schemas import (
    DetectAnomaliesInput,
    DetectAnomaliesOutput,
    Anomaly,
    Severity,
    GetProgramEventsInput,
    ProgramEventsOutput,
    ProgramEvent
)

logger = structlog.get_logger(__name__)


def calculate_severity(deviation_pct: float) -> str:
    """
    Calculate anomaly severity based on deviation percentage

    Args:
        deviation_pct: Percentage deviation from expected

    Returns:
        Severity level: low, medium, high, or critical
    """
    abs_dev = abs(deviation_pct)

    if abs_dev >= 50:
        return "critical"
    elif abs_dev >= 30:
        return "high"
    elif abs_dev >= 15:
        return "medium"
    else:
        return "low"


@tool
async def detect_anomalies(
    program_id: str,
    metric: str = "eaos"
) -> Dict[str, Any]:
    """
    Detect anomalies in program metrics (EAOS, volume, sentiment).

    Identifies unusual patterns or sudden changes in metrics that may
    require producer attention. Uses statistical analysis to find outliers.

    Args:
        program_id: Program or entity identifier
        metric: Metric to analyze - "eaos", "volume", or "sentiment"

    Returns:
        Dictionary with:
        - anomalies: List of detected anomalies with:
          - timestamp: When anomaly occurred
          - metric_value: Actual metric value
          - expected_value: Expected value based on baseline
          - deviation_pct: Percentage deviation
          - severity: "low", "medium", "high", or "critical"
        - program_id: Entity identifier
        - metric: Metric analyzed

    Example:
        >>> result = await detect_anomalies("contestant_1", "eaos")
        >>> for anomaly in result['anomalies']:
        ...     if anomaly['severity'] in ['high', 'critical']:
        ...         print(f"Alert: {anomaly['metric_value']} at {anomaly['timestamp']}")
    """
    try:
        logger.info("Detecting anomalies", program_id=program_id, metric=metric)

        # Get historical data (last 1 hour)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)

        anomalies = []

        if metric == "eaos":
            # Get EAOS timeline
            timeline = clickhouse_client.get_eaos_timeline(
                entity=program_id,
                start_time=start_time,
                end_time=end_time,
                time_window_minutes=5
            )

            if len(timeline) < 3:
                logger.warning("Insufficient data for anomaly detection")
                return {
                    "anomalies": [],
                    "program_id": program_id,
                    "metric": metric,
                    "message": "Insufficient data"
                }

            # Calculate baseline (mean and std dev)
            scores = [p['eaos_score'] for p in timeline]
            mean_score = statistics.mean(scores)
            std_dev = statistics.stdev(scores) if len(scores) > 1 else 0.1

            # Detect outliers (> 2 standard deviations)
            for point in timeline:
                score = point['eaos_score']
                deviation = abs(score - mean_score)

                if deviation > 2 * std_dev:
                    deviation_pct = ((score - mean_score) / mean_score * 100) if mean_score != 0 else 0

                    anomalies.append({
                        "timestamp": point['timestamp'],
                        "metric_value": round(score, 4),
                        "expected_value": round(mean_score, 4),
                        "deviation_pct": round(deviation_pct, 2),
                        "severity": calculate_severity(deviation_pct)
                    })

        elif metric == "volume":
            # Analyze comment volume changes
            # Get comments per 5-minute window
            timeline = clickhouse_client.get_eaos_timeline(
                entity=program_id,
                start_time=start_time,
                end_time=end_time,
                time_window_minutes=5
            )

            if len(timeline) < 3:
                return {
                    "anomalies": [],
                    "program_id": program_id,
                    "metric": metric,
                    "message": "Insufficient data"
                }

            volumes = [p['comment_count'] for p in timeline]
            mean_volume = statistics.mean(volumes)
            std_dev = statistics.stdev(volumes) if len(volumes) > 1 else max(mean_volume * 0.5, 1)

            for point in timeline:
                volume = point['comment_count']
                deviation = abs(volume - mean_volume)

                if deviation > 2 * std_dev:
                    deviation_pct = ((volume - mean_volume) / mean_volume * 100) if mean_volume != 0 else 0

                    anomalies.append({
                        "timestamp": point['timestamp'],
                        "metric_value": volume,
                        "expected_value": round(mean_volume, 1),
                        "deviation_pct": round(deviation_pct, 2),
                        "severity": calculate_severity(deviation_pct)
                    })

        elif metric == "sentiment":
            # Analyze sentiment score changes
            timeline = clickhouse_client.get_eaos_timeline(
                entity=program_id,
                start_time=start_time,
                end_time=end_time,
                time_window_minutes=5
            )

            if len(timeline) < 3:
                return {
                    "anomalies": [],
                    "program_id": program_id,
                    "metric": metric,
                    "message": "Insufficient data"
                }

            sentiments = [p['sentiment_score'] for p in timeline]
            mean_sentiment = statistics.mean(sentiments)
            std_dev = statistics.stdev(sentiments) if len(sentiments) > 1 else 0.2

            for point in timeline:
                sentiment = point['sentiment_score']
                deviation = abs(sentiment - mean_sentiment)

                if deviation > 2 * std_dev:
                    deviation_pct = abs((sentiment - mean_sentiment) / (abs(mean_sentiment) + 0.01) * 100)

                    anomalies.append({
                        "timestamp": point['timestamp'],
                        "metric_value": round(sentiment, 4),
                        "expected_value": round(mean_sentiment, 4),
                        "deviation_pct": round(deviation_pct, 2),
                        "severity": calculate_severity(deviation_pct)
                    })

        # Sort by timestamp
        anomalies.sort(key=lambda x: x['timestamp'], reverse=True)

        return {
            "anomalies": anomalies[:10],  # Return top 10
            "program_id": program_id,
            "metric": metric,
            "total_anomalies": len(anomalies)
        }

    except Exception as e:
        logger.error("Failed to detect anomalies", error=str(e))
        return {
            "anomalies": [],
            "program_id": program_id,
            "metric": metric,
            "error": str(e)
        }


@tool
async def get_program_events(
    program_id: str,
    time: str
) -> Dict[str, Any]:
    """
    Get program events around a specific time.

    Retrieves notable events (segment changes, contestant appearances, etc.)
    that occurred near the specified time. Helps correlate metrics with events.

    Args:
        program_id: Program identifier
        time: Target time (ISO format: "2024-01-01T19:30:00")

    Returns:
        Dictionary with:
        - events: List of program events with:
          - timestamp: Event time
          - event_type: Type of event
          - description: Event description
        - program_id: Program identifier

    Example:
        >>> result = await get_program_events("show_1", "2024-01-01T19:30:00")
        >>> for event in result['events']:
        ...     print(f"{event['timestamp']}: {event['description']}")

    Note:
        This is a mock implementation. In production, integrate with
        your program scheduling system or manual event logging.
    """
    try:
        logger.info("Getting program events", program_id=program_id, time=time)

        target_time = datetime.fromisoformat(time)

        # Mock events (in production, query from events database)
        # For now, infer events from comment volume and EAOS changes

        start_time = target_time - timedelta(minutes=30)
        end_time = target_time + timedelta(minutes=30)

        # Get timeline to infer events
        timeline = clickhouse_client.get_eaos_timeline(
            entity=program_id,
            start_time=start_time,
            end_time=end_time,
            time_window_minutes=5
        )

        events = []

        # Infer events from metric changes
        for i in range(1, len(timeline)):
            prev = timeline[i-1]
            curr = timeline[i]

            # Detect significant volume spike (new segment/contestant)
            if curr['comment_count'] > prev['comment_count'] * 1.5:
                events.append({
                    "timestamp": curr['timestamp'],
                    "event_type": "volume_spike",
                    "description": f"Sudden increase in viewer engagement ({curr['comment_count']} comments)"
                })

            # Detect EAOS drop (potential issue)
            if curr['eaos_score'] < prev['eaos_score'] * 0.8:
                events.append({
                    "timestamp": curr['timestamp'],
                    "event_type": "eaos_drop",
                    "description": f"EAOS dropped from {prev['eaos_score']:.2f} to {curr['eaos_score']:.2f}"
                })

        # Add some common program events (mock)
        events.extend([
            {
                "timestamp": target_time,
                "event_type": "segment",
                "description": "Program segment (inferred)"
            }
        ])

        # Sort by timestamp
        events.sort(key=lambda x: x['timestamp'])

        return {
            "events": events,
            "program_id": program_id,
            "time_range": {
                "start": start_time,
                "end": end_time
            }
        }

    except Exception as e:
        logger.error("Failed to get program events", error=str(e))
        return {
            "events": [],
            "program_id": program_id,
            "error": str(e)
        }
