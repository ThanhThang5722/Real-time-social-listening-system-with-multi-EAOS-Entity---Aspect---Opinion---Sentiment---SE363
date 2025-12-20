from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatMessage, AnalyticsSummary
from services.eaos_analyzer import EAOSAnalyzerService
from datetime import datetime
import random

router = APIRouter()

# Global analyzer instance (in production, use dependency injection)
analyzer = EAOSAnalyzerService()


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
