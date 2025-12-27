"""
Add Test Comments to MongoDB

This script adds unlabeled comments to MongoDB so Airflow can process them
"""

from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
MONGO_URL = "mongodb://admin:admin123@localhost:27017/"

# Test comments
TEST_COMMENTS = [
    "MC Trấn Thành dẫn chương trình rất hay và vui nhộn",
    "Kịch bản của Running Man Việt Nam rất cuốn hút",
    "Dàn cast chơi trò chơi rất tốt và vui vẻ",
    "Địa điểm quay phim đẹp và ấn tượng",
    "Khách mời tuần này không hay lắm, hơi nhàm chán",
    "Thử thách trong tập này quá khó, các thành viên không làm được",
    "MC dẫn tốt nhưng kịch bản chưa hay",
    "Chương trình vui nhộn, tôi rất thích xem",
    "Quảng cáo quá nhiều, làm gián đoạn chương trình",
    "Tương tác giữa các thành viên rất tự nhiên và vui",
    "Tinh thần đồng đội của team rất tốt",
    "Trò chơi hôm nay rất hay và kịch tính",
    "Giọng của MC rõ ràng và dễ nghe",
    "Nội dung chương trình hơi lặp lại so với mùa trước",
    "Dàn dựng của chương trình rất chuyên nghiệp",
]

def add_test_comments():
    """Add test comments to MongoDB"""
    print("=" * 70)
    print("  Adding Test Comments to MongoDB")
    print("=" * 70)

    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URL)
        db = client['tv_analytics']
        collection = db['comments']

        # Test connection
        client.server_info()
        print(f"✅ Connected to MongoDB")

        # Check current unlabeled count
        current_unlabeled = collection.count_documents({
            '$or': [
                {'labels': {'$exists': False}},
                {'labels': {'$size': 0}}
            ]
        })

        print(f"\n📊 Current unlabeled comments: {current_unlabeled}")

        # Add comments
        print(f"\n📝 Adding {len(TEST_COMMENTS)} test comments...")

        inserted_ids = []
        for i, text in enumerate(TEST_COMMENTS, 1):
            result = collection.insert_one({
                'text': text,
                'source': 'test_script',
                'created_at': datetime.now(),
                'labels': []  # Empty - will be filled by Airflow
            })

            inserted_ids.append(result.inserted_id)
            print(f"   {i}. Added: {text[:50]}...")

        print(f"\n✅ Successfully added {len(inserted_ids)} comments")

        # Check new unlabeled count
        new_unlabeled = collection.count_documents({
            '$or': [
                {'labels': {'$exists': False}},
                {'labels': {'$size': 0}}
            ]
        })

        print(f"\n📊 New unlabeled comments: {new_unlabeled}")
        print(f"   Increase: +{new_unlabeled - current_unlabeled}")

        # Show sample
        print(f"\n📋 Sample unlabeled comment:")
        sample = collection.find_one({'labels': {'$size': 0}})
        if sample:
            print(f"   ID: {sample['_id']}")
            print(f"   Text: {sample['text']}")
            print(f"   Labels: {sample['labels']}")
            print(f"   Source: {sample['source']}")

        print("\n" + "=" * 70)
        print("✅ Test comments added successfully!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Trigger Airflow DAG:")
        print("     docker exec -it tv-analytics-airflow-scheduler \\")
        print("       airflow dags trigger batch_prediction")
        print("\n  2. Watch Airflow logs:")
        print("     docker compose logs -f airflow-scheduler")
        print("\n  3. Check for PySpark calls in logs:")
        print("     docker compose logs airflow-scheduler | grep -i pyspark")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    add_test_comments()
