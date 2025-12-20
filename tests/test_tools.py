"""Test Agent Tools"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import pytest
from datetime import datetime, timedelta

from src.storage.redis_client import redis_client
from src.storage.clickhouse_client import clickhouse_client
from src.storage.elasticsearch_client import elasticsearch_client

from src.agent.tools.eaos_tools import get_current_eaos, get_eaos_timeline
from src.agent.tools.trend_tools import get_trending_topics, get_topic_details
from src.agent.tools.search_tools import search_comments, get_sample_comments
from src.agent.tools.anomaly_tools import detect_anomalies, get_program_events
from src.agent.tools.recommendation_tools import generate_recommendation


@pytest.fixture(scope="session")
async def setup_connections():
    """Setup database connections"""
    await redis_client.connect()
    clickhouse_client.connect()
    await elasticsearch_client.connect()

    yield

    await redis_client.disconnect()
    clickhouse_client.disconnect()
    await elasticsearch_client.disconnect()


@pytest.mark.asyncio
async def test_get_current_eaos(setup_connections):
    """Test get_current_eaos tool"""
    result = await get_current_eaos.ainvoke({"program_id": "chương trình"})

    print("\n=== Test get_current_eaos ===")
    print(f"Score: {result.get('score')}")
    print(f"Positive %: {result.get('positive_pct')}")
    print(f"Negative %: {result.get('negative_pct')}")
    print(f"Total Comments: {result.get('total_comments')}")

    assert 'score' in result
    assert isinstance(result['score'], (int, float))


@pytest.mark.asyncio
async def test_get_eaos_timeline(setup_connections):
    """Test get_eaos_timeline tool"""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)

    result = await get_eaos_timeline.ainvoke({
        "program_id": "chương trình",
        "from_time": start_time.isoformat(),
        "to_time": end_time.isoformat(),
        "granularity": "5min"
    })

    print("\n=== Test get_eaos_timeline ===")
    print(f"Timeline points: {len(result.get('timeline', []))}")
    if result.get('timeline'):
        print(f"First point: {result['timeline'][0]}")

    assert 'timeline' in result
    assert isinstance(result['timeline'], list)


@pytest.mark.asyncio
async def test_get_trending_topics(setup_connections):
    """Test get_trending_topics tool"""
    result = await get_trending_topics.ainvoke({
        "limit": 5,
        "time_range": "1hour"
    })

    print("\n=== Test get_trending_topics ===")
    print(f"Found {len(result.get('topics', []))} trending topics:")
    for topic in result.get('topics', [])[:5]:
        print(f"  - {topic['topic']}: {topic['count']} mentions (sentiment: {topic['sentiment']})")

    assert 'topics' in result
    assert isinstance(result['topics'], list)


@pytest.mark.asyncio
async def test_search_comments(setup_connections):
    """Test search_comments tool"""
    result = await search_comments.ainvoke({
        "query": "chương trình",
        "limit": 5
    })

    print("\n=== Test search_comments ===")
    print(f"Found {result.get('total_found')} comments")
    for comment in result.get('comments', [])[:3]:
        print(f"  - [{comment['sentiment']}] {comment['text'][:80]}...")

    assert 'comments' in result
    assert 'total_found' in result


@pytest.mark.asyncio
async def test_detect_anomalies(setup_connections):
    """Test detect_anomalies tool"""
    result = await detect_anomalies.ainvoke({
        "program_id": "chương trình",
        "metric": "eaos"
    })

    print("\n=== Test detect_anomalies ===")
    print(f"Found {len(result.get('anomalies', []))} anomalies")
    for anomaly in result.get('anomalies', [])[:3]:
        print(f"  - {anomaly['timestamp']}: {anomaly['metric_value']} (deviation: {anomaly['deviation_pct']}%, severity: {anomaly['severity']})")

    assert 'anomalies' in result
    assert isinstance(result['anomalies'], list)


def test_generate_recommendation():
    """Test generate_recommendation tool"""
    context = "EAOS for contestant_1 dropped 40% in last 5 minutes. Negative comments mention 'unfair scoring'."

    result = generate_recommendation.invoke({"context": context})

    print("\n=== Test generate_recommendation ===")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Reasoning: {result['reasoning']}")

    assert 'recommendation' in result
    assert 'confidence' in result
    assert 'reasoning' in result


async def run_all_tests():
    """Run all tests"""
    print("Starting Agent Tools Tests\n")

    # Setup
    await redis_client.connect()
    clickhouse_client.connect()
    await elasticsearch_client.connect()

    try:
        # Run tests
        await test_get_current_eaos(None)
        await test_get_eaos_timeline(None)
        await test_get_trending_topics(None)
        await test_search_comments(None)
        await test_detect_anomalies(None)
        test_generate_recommendation()

        print("\n✅ All tests completed!")

    finally:
        # Cleanup
        await redis_client.disconnect()
        clickhouse_client.disconnect()
        await elasticsearch_client.disconnect()


if __name__ == "__main__":
    # Setup logging
    import structlog
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )

    asyncio.run(run_all_tests())
