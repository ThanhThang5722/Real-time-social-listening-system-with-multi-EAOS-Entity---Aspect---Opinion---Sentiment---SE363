"""Test AI Agent workflow"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import structlog
from src.agent.orchestrator import query_agent


# Setup logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)


async def test_status_check():
    """Test status check query"""
    print("\n" + "="*80)
    print("TEST 1: Status Check - How is a contestant performing?")
    print("="*80)

    query = "How is chương trình performing right now?"

    response = await query_agent(query, verbose=True)

    print("\n📊 RESPONSE:")
    print(response['response'])

    print("\n📋 METADATA:")
    for key, value in response['metadata'].items():
        print(f"  {key}: {value}")

    if response.get('debug'):
        print("\n🔍 DEBUG INFO:")
        print("\nReasoning Trace:")
        for trace in response['debug']['reasoning_trace']:
            print(f"  - {trace}")

        print("\nTools Used:")
        for tool in response['metadata']['tools_used']:
            print(f"  - {tool}")


async def test_trending():
    """Test trending topics query"""
    print("\n" + "="*80)
    print("TEST 2: Trending - What's trending now?")
    print("="*80)

    query = "What topics are trending in the last 15 minutes?"

    response = await query_agent(query, verbose=False)

    print("\n📊 RESPONSE:")
    print(response['response'])

    print("\n📋 METADATA:")
    print(f"  Intent: {response['metadata']['intent']}")
    print(f"  Tools Used: {response['metadata']['tools_used']}")
    print(f"  Processing Time: {response['metadata']['processing_time_seconds']:.2f}s")


async def test_investigation():
    """Test investigation query"""
    print("\n" + "="*80)
    print("TEST 3: Investigation - Why did metrics change?")
    print("="*80)

    query = "Are there any anomalies in EAOS for chương trình?"

    response = await query_agent(query, verbose=True)

    print("\n📊 RESPONSE:")
    print(response['response'])

    print("\n📋 METADATA:")
    for key, value in response['metadata'].items():
        print(f"  {key}: {value}")


async def test_search():
    """Test search query"""
    print("\n" + "="*80)
    print("TEST 4: Search - Find specific comments")
    print("="*80)

    query = "Show me negative comments about chương trình"

    response = await query_agent(query, verbose=False)

    print("\n📊 RESPONSE:")
    print(response['response'])

    print("\n📋 METADATA:")
    print(f"  Intent: {response['metadata']['intent']}")
    print(f"  Confidence: {response['metadata']['confidence']}")
    print(f"  Iterations: {response['metadata']['iterations']}")


async def test_comparison():
    """Test comparison query"""
    print("\n" + "="*80)
    print("TEST 5: Comparison - Compare two entities")
    print("="*80)

    # This will work better if you have two entities in your data
    query = "Compare the performance of chương trình and madison media group"

    response = await query_agent(query, verbose=False)

    print("\n📊 RESPONSE:")
    print(response['response'])


async def run_all_tests():
    """Run all agent tests"""
    print("\n" + "="*80)
    print("TV PRODUCER ANALYTICS AI AGENT - TEST SUITE")
    print("="*80)

    print("\n⚠️  Make sure you have:")
    print("  1. Started Docker services (docker-compose up -d)")
    print("  2. Initialized databases (python scripts/init_databases.py)")
    print("  3. Seeded sample data (python scripts/seed_sample_data.py --count 100)")
    print("  4. Set up GCP credentials in .env")

    input("\nPress Enter to start tests...")

    try:
        # Run tests
        await test_status_check()
        await asyncio.sleep(1)

        await test_trending()
        await asyncio.sleep(1)

        await test_investigation()
        await asyncio.sleep(1)

        await test_search()
        await asyncio.sleep(1)

        await test_comparison()

        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED!")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def interactive_mode():
    """Interactive mode to test agent queries"""
    print("\n" + "="*80)
    print("TV PRODUCER ANALYTICS AI AGENT - INTERACTIVE MODE")
    print("="*80)
    print("\nType your questions (or 'quit' to exit)")
    print("Examples:")
    print("  - How is contestant 1 doing?")
    print("  - What's trending now?")
    print("  - Why did EAOS drop?")
    print("  - Show me negative comments")
    print("\n" + "="*80 + "\n")

    while True:
        try:
            query = input("Producer Query: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋")
                break

            if not query:
                continue

            print("\n🤖 Agent is thinking...\n")

            response = await query_agent(query, verbose=False)

            print("\n📊 RESPONSE:")
            print("-" * 80)
            print(response['response'])
            print("-" * 80)

            print(f"\n💡 Intent: {response['metadata']['intent']} | "
                  f"Tools: {', '.join(response['metadata']['tools_used'])} | "
                  f"Time: {response['metadata']['processing_time_seconds']:.2f}s")
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test AI Agent")
    parser.add_argument(
        "--mode",
        choices=["test", "interactive"],
        default="test",
        help="Test mode: 'test' runs predefined tests, 'interactive' allows custom queries"
    )

    args = parser.parse_args()

    if args.mode == "test":
        asyncio.run(run_all_tests())
    else:
        asyncio.run(interactive_mode())
