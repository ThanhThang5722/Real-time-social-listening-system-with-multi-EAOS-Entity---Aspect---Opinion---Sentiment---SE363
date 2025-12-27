import sys
import httpx
from pymongo import MongoClient

def test():
    # Fetch comments
    client = MongoClient("mongodb://admin:admin123@mongodb:27017/")
    db = client["tv_analytics"]
    collection = db["comments"]

    comments = list(collection.find(
        {
            "$or": [
                {"labels": {"$exists": False}},
                {"labels": {"$size": 0}}
            ]
        },
        {"_id": 1, "text": 1}
    ).limit(5))

    # Convert ObjectId to string
    for comment in comments:
        comment["_id"] = str(comment["_id"])

    print(f"Fetched {len(comments)} comments")

    if len(comments) == 0:
        print("No comments to process")
        return

    # Call PySpark
    pyspark_url = "http://pyspark:5001"
    request_data = {
        "comments": [
            {"id": str(c["_id"]), "text": c["text"]}
            for c in comments
        ]
    }

    print(f"Calling {pyspark_url}/predict/batch...")

    try:
        with httpx.Client(timeout=60.0) as http_client:
            response = http_client.post(
                f"{pyspark_url}/predict/batch",
                json=request_data
            )

            print(f"Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()

            method = result.get("method")
            count = result.get("count")
            print(f"Success! Method: {method}, Count: {count}")
            return result

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    test()
