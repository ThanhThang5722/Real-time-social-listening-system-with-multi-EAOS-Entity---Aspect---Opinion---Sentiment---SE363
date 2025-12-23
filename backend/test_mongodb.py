"""
Test script for MongoDB Repository

Usage:
    python test_mongodb.py connection  # Test connection only
    python test_mongodb.py insert      # Test inserting comments
    python test_mongodb.py query       # Test querying data
    python test_mongodb.py stats       # Show database statistics
    python test_mongodb.py export      # Export training data
"""
import asyncio
import sys
from datetime import datetime
from services.mongodb_repository import MongoDBRepository
from models.schemas import Comment, EAOSLabel


async def test_connection():
    """Test MongoDB connection"""
    print("=" * 60)
    print("Testing MongoDB Connection")
    print("=" * 60)

    repo = MongoDBRepository()

    try:
        await repo.connect()
        print("\n✓ Connected successfully")

        # Get stats
        stats = await repo.get_statistics()
        print(f"\nDatabase Statistics:")
        print(f"  Total comments: {stats.get('total_comments', 0)}")
        print(f"  Sentiment distribution: {stats.get('sentiment_distribution', {})}")

        return True

    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        return False
    finally:
        await repo.disconnect()


async def test_insert():
    """Test inserting sample comments"""
    print("=" * 60)
    print("Testing MongoDB Insert Operations")
    print("=" * 60)

    repo = MongoDBRepository()

    try:
        await repo.connect()
        print("\n✓ Connected to MongoDB")

        # Create sample comments
        sample_comments = [
            Comment(
                id=f"test_comment_{i}_{datetime.now().timestamp()}",
                text=text,
                labels=[
                    EAOSLabel(
                        entity=entity,
                        aspect=aspect,
                        opinion=opinion,
                        sentiment=sentiment
                    )
                ],
                timestamp=datetime.now(),
                username=f"test_user_{i}"
            )
            for i, (text, entity, aspect, opinion, sentiment) in enumerate([
                ("Chương trình rất hay và bổ ích!", "chương trình", "Nội dung", "rất hay", "tích cực"),
                ("Diễn viên diễn xuất tuyệt vời", "diễn viên", "Diễn xuất", "tuyệt vời", "tích cực"),
                ("Âm thanh hơi nhỏ, khó nghe", "âm thanh", "Kỹ thuật", "hơi nhỏ", "tiêu cực"),
                ("Kịch bản phim này rất cuốn", "phim", "Kịch bản", "rất cuốn", "tích cực"),
                ("Mùa này không hay bằng mùa trước", "mùa", "Chất lượng", "không hay", "tiêu cực")
            ])
        ]

        print(f"\nInserting {len(sample_comments)} sample comments...")

        # Insert individually
        success_count = 0
        for comment in sample_comments:
            if await repo.save_comment(comment):
                success_count += 1

        print(f"\n✓ Successfully inserted {success_count}/{len(sample_comments)} comments")

        # Get updated stats
        total = await repo.get_comments_count()
        print(f"Total comments in database: {total}")

    except Exception as e:
        print(f"\n✗ Insert failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repo.disconnect()


async def test_query():
    """Test querying comments"""
    print("=" * 60)
    print("Testing MongoDB Query Operations")
    print("=" * 60)

    repo = MongoDBRepository()

    try:
        await repo.connect()
        print("\n✓ Connected to MongoDB")

        # Get recent comments
        print("\n--- Recent Comments (5) ---")
        recent = await repo.get_recent_comments(limit=5)
        for i, comment in enumerate(recent, 1):
            print(f"\n{i}. ID: {comment.get('id')}")
            print(f"   Text: {comment.get('text', '')[:50]}...")
            print(f"   User: {comment.get('username')}")
            print(f"   Sentiment: {comment['labels'][0]['sentiment'] if comment.get('labels') else 'N/A'}")

        # Get by sentiment
        print("\n--- Positive Comments (3) ---")
        positive = await repo.get_comments_by_sentiment("tích cực", limit=3)
        for i, comment in enumerate(positive, 1):
            print(f"{i}. {comment.get('text', '')[:60]}...")

        print("\n--- Negative Comments (3) ---")
        negative = await repo.get_comments_by_sentiment("tiêu cực", limit=3)
        for i, comment in enumerate(negative, 1):
            print(f"{i}. {comment.get('text', '')[:60]}...")

    except Exception as e:
        print(f"\n✗ Query failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repo.disconnect()


async def test_statistics():
    """Show database statistics"""
    print("=" * 60)
    print("MongoDB Database Statistics")
    print("=" * 60)

    repo = MongoDBRepository()

    try:
        await repo.connect()
        stats = await repo.get_statistics()

        print(f"\n📊 Overall Statistics:")
        print(f"   Total comments: {stats.get('total_comments', 0)}")

        print(f"\n📈 Sentiment Distribution:")
        for sentiment, count in stats.get('sentiment_distribution', {}).items():
            print(f"   {sentiment}: {count}")

        print(f"\n💾 Collections:")
        for name, collection in stats.get('collections', {}).items():
            print(f"   {name}: {collection}")

    except Exception as e:
        print(f"\n✗ Error getting statistics: {e}")
    finally:
        await repo.disconnect()


async def test_export():
    """Test exporting training data"""
    print("=" * 60)
    print("Testing Training Data Export")
    print("=" * 60)

    repo = MongoDBRepository()

    try:
        await repo.connect()
        print("\n✓ Connected to MongoDB")

        # Export training data
        print("\nExporting training data...")
        result = await repo.export_training_data()

        print(f"\n✓ Export completed:")
        print(f"   Export ID: {result.get('export_id')}")
        print(f"   Total comments: {result.get('total_comments')}")
        print(f"   Exported at: {result.get('exported_at')}")

        # Preview some training data
        print("\n--- Sample Training Data (3 items) ---")
        training_data = await repo.get_training_data(limit=3)
        for i, item in enumerate(training_data, 1):
            print(f"\n{i}. Text: {item.get('text', '')[:50]}...")
            print(f"   Labels: {len(item.get('labels', []))} EAOS labels")

    except Exception as e:
        print(f"\n✗ Export failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repo.disconnect()


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "connection"

    print("\n" + "=" * 60)
    print("MongoDB Test Script")
    print("=" * 60)
    print("\nMake sure MongoDB is running:")
    print("  docker-compose up -d mongodb")
    print("=" * 60 + "\n")

    try:
        if mode == "connection":
            await test_connection()
        elif mode == "insert":
            await test_insert()
        elif mode == "query":
            await test_query()
        elif mode == "stats":
            await test_statistics()
        elif mode == "export":
            await test_export()
        else:
            print(f"Unknown mode: {mode}")
            print("\nAvailable modes:")
            print("  connection  - Test connection")
            print("  insert      - Insert sample data")
            print("  query       - Query data")
            print("  stats       - Show statistics")
            print("  export      - Export training data")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
