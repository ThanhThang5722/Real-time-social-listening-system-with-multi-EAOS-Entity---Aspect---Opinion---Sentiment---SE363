from fastapi import APIRouter, HTTPException
from models.schemas import (
    ChatRequest,
    ChatMessage,
    AnalyticsSummary,
    PredictRequest,
    PredictBatchRequest,
    PredictResponse
)
from services.eaos_analyzer import EAOSAnalyzerService
from pymongo import MongoClient
from datetime import datetime
from typing import List
import random

router = APIRouter()

# Global instances (in production, use dependency injection)
analyzer = EAOSAnalyzerService()
mongo_client = None


def get_mongo_client():
    """Get MongoDB client"""
    global mongo_client
    if mongo_client is None:
        import os
        # Use environment variable or default to localhost (for local development)
        mongo_host = os.getenv('MONGO_HOST', 'localhost')
        mongo_url = f'mongodb://admin:admin123@{mongo_host}:27017/'
        mongo_client = MongoClient(mongo_url)
        print(f"✅ Connected to MongoDB at {mongo_host}:27017")
    return mongo_client


@router.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "EAOS Dashboard API"}


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary():
    """Get analytics summary of all comments"""
    return analyzer.get_analytics_summary()


@router.get("/analytics/sentiment-trend")
async def get_sentiment_trend():
    """Get sentiment trend over time"""
    return analyzer.get_sentiment_trend()


@router.post("/chat", response_model=ChatMessage)
async def chat(request: ChatRequest):
    """Chat endpoint for Q&A about comments (mock implementation)"""

    # Mock chatbot responses based on keywords
    message_lower = request.message.lower()

    if "tổng quan" in message_lower or "summary" in message_lower or "tóm tắt" in message_lower:
        response_text = analyzer.generate_summary_text()

    elif "sentiment" in message_lower or "cảm xúc" in message_lower:
        summary = analyzer.get_analytics_summary()
        sentiment_dist = summary.sentiment_distribution
        total = sum(sentiment_dist.values())
        response_text = "Phân bố cảm xúc hiện tại:\n"
        for sentiment, count in sentiment_dist.items():
            percentage = (count / total) * 100 if total > 0 else 0
            response_text += f"- {sentiment.capitalize()}: {count} bình luận ({percentage:.1f}%)\n"

    elif "entity" in message_lower or "thực thể" in message_lower:
        summary = analyzer.get_analytics_summary()
        top_entities = summary.top_entities[:5]
        response_text = "Top 5 thực thể được nhắc đến nhiều nhất:\n"
        for item in top_entities:
            response_text += f"- {item['entity']}: {item['count']} lần\n"

    elif "aspect" in message_lower or "khía cạnh" in message_lower:
        summary = analyzer.get_analytics_summary()
        top_aspects = summary.top_aspects[:5]
        response_text = "Top 5 khía cạnh được đề cập nhiều nhất:\n"
        for item in top_aspects:
            response_text += f"- {item['aspect']}: {item['count']} lần\n"

    elif "search" in message_lower or "tìm" in message_lower:
        # Extract search query (simple implementation)
        query = request.message.split("search")[-1].split("tìm")[-1].strip()
        results = analyzer.search_comments(query)
        response_text = f"Tìm thấy {len(results)} bình luận chứa '{query}'."
        if results:
            response_text += "\n\nVí dụ:\n"
            for comment in results[:3]:
                response_text += f"- {comment.text[:100]}...\n"

    elif "problem" in message_lower or "vấn đề" in message_lower or "issue" in message_lower:
        summary = analyzer.get_analytics_summary()
        negative_count = summary.sentiment_distribution.get("tiêu cực", 0)
        total = summary.total_comments

        if negative_count > 0:
            percentage = (negative_count / total) * 100
            response_text = f"Phát hiện {negative_count} bình luận tiêu cực ({percentage:.1f}%).\n\n"
            response_text += "Các vấn đề thường gặp:\n"

            # Find common negative aspects
            negative_aspects = []
            for comment in analyzer.comments_buffer:
                for label in comment.labels:
                    if label.sentiment == "tiêu cực":
                        negative_aspects.append(label.aspect)

            from collections import Counter
            aspect_counter = Counter(negative_aspects)
            for aspect, count in aspect_counter.most_common(5):
                response_text += f"- {aspect}: {count} lần\n"
        else:
            response_text = "Hiện tại không phát hiện vấn đề nghiêm trọng. Hầu hết bình luận đều tích cực!"

    else:
        # Default response
        responses = [
            "Tôi có thể giúp bạn phân tích bình luận. Hãy hỏi tôi về: tổng quan, cảm xúc, thực thể, khía cạnh, hoặc vấn đề.",
            "Bạn muốn biết điều gì về các bình luận? Tôi có thể tóm tắt, tìm kiếm, hoặc phân tích cảm xúc.",
            "Hãy hỏi tôi về: 'tổng quan', 'cảm xúc', 'thực thể', 'khía cạnh', hoặc 'vấn đề' để biết thêm chi tiết."
        ]
        response_text = random.choice(responses)

    return ChatMessage(
        role="assistant",
        content=response_text,
        timestamp=datetime.now()
    )


@router.get("/search")
async def search_comments(q: str, limit: int = 20):
    """Search comments by text"""
    results = analyzer.search_comments(q)
    return {
        "query": q,
        "count": len(results),
        "results": results[:limit]
    }


@router.post("/submit", response_model=dict)
async def submit_comment(request: PredictRequest):
    """
    Submit comment to MongoDB for batch processing

    Flow: Backend → MongoDB (unlabeled) → Wait for Airflow → Airflow → PySpark → MongoDB (labeled)

    Args:
        request: PredictRequest with text

    Returns:
        Confirmation with comment ID
    """
    try:
        # Save to MongoDB without labels (to be processed by Airflow)
        client = get_mongo_client()
        db = client['tv_analytics']
        collection = db['comments']

        result = collection.insert_one({
            'text': request.text,
            'source': 'api',
            'created_at': datetime.now(),
            'labels': []  # Empty - will be filled by Airflow batch processing
        })

        return {
            "status": "submitted",
            "comment_id": str(result.inserted_id),
            "message": "Comment saved to MongoDB. Will be processed in next batch (every 15 min).",
            "text": request.text
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit comment: {str(e)}"
        )


@router.post("/submit/batch")
async def submit_batch_comments(request: PredictBatchRequest):
    """
    Submit multiple comments to MongoDB for batch processing

    Flow: Backend → MongoDB (unlabeled) → Wait for Airflow → Airflow → PySpark → MongoDB (labeled)

    Args:
        request: PredictBatchRequest with list of texts

    Returns:
        Confirmation with count and IDs
    """
    try:
        # Save all to MongoDB without labels
        client = get_mongo_client()
        db = client['tv_analytics']
        collection = db['comments']

        documents = [
            {
                'text': text,
                'source': 'api_batch',
                'created_at': datetime.now(),
                'labels': []  # Empty - will be filled by Airflow
            }
            for text in request.texts
        ]

        result = collection.insert_many(documents)

        return {
            "status": "submitted",
            "count": len(result.inserted_ids),
            "comment_ids": [str(id) for id in result.inserted_ids],
            "message": f"Saved {len(result.inserted_ids)} comments to MongoDB. Will be processed in next batch (every 15 min)."
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit batch: {str(e)}"
        )


@router.get("/comments/labeled")
async def get_labeled_comments(limit: int = 100, skip: int = 0):
    """
    Get labeled comments from MongoDB (after Airflow batch processing)

    Returns comments that have been processed by Airflow with Entity, Aspect, Opinion, Sentiment predictions

    Query params:
        limit: Maximum number of comments to return (default: 100)
        skip: Number of comments to skip (for pagination)
    """
    try:
        client = get_mongo_client()
        db = client['tv_analytics']
        collection = db['comments']

        # Query ONLY labeled comments (processed by Airflow)
        labeled_comments = list(collection.find(
            {'labels': {'$exists': True, '$ne': []}},
            {'_id': 1, 'text': 1, 'labels': 1, 'predicted_at': 1, 'created_at': 1, 'source': 1}
        ).sort('predicted_at', -1).skip(skip).limit(limit))

        # Convert ObjectId to string and format dates
        for comment in labeled_comments:
            comment['_id'] = str(comment['_id'])
            comment['created_at'] = comment['created_at'].isoformat() if comment.get('created_at') else None
            comment['predicted_at'] = comment['predicted_at'].isoformat() if comment.get('predicted_at') else None

        return {
            "total": len(labeled_comments),
            "comments": labeled_comments
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get labeled comments: {str(e)}"
        )


@router.get("/comments/{comment_id}")
async def get_comment_by_id(comment_id: str):
    """
    Get a specific comment by ID to check if predictions are ready

    Frontend can poll this endpoint after submitting to check when predictions are available

    Args:
        comment_id: MongoDB ObjectId of the comment

    Returns:
        Comment with predictions (if processed) and status
    """
    from bson import ObjectId

    try:
        client = get_mongo_client()
        db = client['tv_analytics']
        collection = db['comments']

        comment = collection.find_one({'_id': ObjectId(comment_id)})

        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        # Convert ObjectId to string and format dates
        comment['_id'] = str(comment['_id'])
        comment['created_at'] = comment['created_at'].isoformat() if comment.get('created_at') else None
        if comment.get('predicted_at'):
            comment['predicted_at'] = comment['predicted_at'].isoformat()

        # Check if labeled
        is_labeled = bool(comment.get('labels') and len(comment['labels']) > 0)

        return {
            "comment": comment,
            "is_labeled": is_labeled,
            "status": "labeled" if is_labeled else "pending",
            "message": "Predictions ready!" if is_labeled else "Waiting for batch processing (runs every 1 min)"
        }

    except Exception as e:
        raise HTTPException(
            status_code=400 if "ObjectId" in str(e) else 500,
            detail=str(e)
        )
