from typing import List, Dict
from collections import Counter
from models.schemas import Comment, AnalyticsSummary


class EAOSAnalyzerService:
    """Service for analyzing EAOS data (mock implementation)"""

    def __init__(self):
        self.comments_buffer: List[Comment] = []
        self.max_buffer_size = 1000

    def add_comment(self, comment: Comment):
        """Add comment to buffer for analysis"""
        self.comments_buffer.append(comment)
        if len(self.comments_buffer) > self.max_buffer_size:
            self.comments_buffer.pop(0)

    def get_analytics_summary(self) -> AnalyticsSummary:
        """Generate analytics summary from buffered comments"""
        if not self.comments_buffer:
            return AnalyticsSummary(
                total_comments=0,
                sentiment_distribution={},
                top_entities=[],
                top_aspects=[],
                recent_comments=[]
            )

        # Count sentiments
        sentiment_counter = Counter()
        entity_counter = Counter()
        aspect_counter = Counter()

        for comment in self.comments_buffer:
            for label in comment.labels:
                sentiment_counter[label.sentiment] += 1
                entity_counter[label.entity] += 1
                aspect_counter[label.aspect] += 1

        # Get top entities and aspects
        top_entities = [
            {"entity": entity, "count": count}
            for entity, count in entity_counter.most_common(10)
        ]

        top_aspects = [
            {"aspect": aspect, "count": count}
            for aspect, count in aspect_counter.most_common(10)
        ]

        # Get recent comments (last 20)
        recent_comments = self.comments_buffer[-20:]

        return AnalyticsSummary(
            total_comments=len(self.comments_buffer),
            sentiment_distribution=dict(sentiment_counter),
            top_entities=top_entities,
            top_aspects=top_aspects,
            recent_comments=recent_comments
        )

    def search_comments(self, query: str) -> List[Comment]:
        """Search comments by text (simple mock search)"""
        query_lower = query.lower()
        results = [
            comment for comment in self.comments_buffer
            if query_lower in comment.text.lower()
        ]
        return results[:50]  # Return max 50 results

    def get_sentiment_trend(self) -> Dict:
        """Get sentiment trend over time (mock implementation)"""
        # For now, just return current distribution
        # In real implementation, this would track sentiment over time windows
        summary = self.get_analytics_summary()
        return {
            "timestamps": ["now"],
            "sentiments": summary.sentiment_distribution
        }

    def generate_summary_text(self) -> str:
        """Generate text summary for chatbot (mock)"""
        summary = self.get_analytics_summary()

        if summary.total_comments == 0:
            return "Chưa có bình luận nào được phân tích."

        # Calculate sentiment percentages
        total = summary.total_comments
        sentiment_text = []
        for sentiment, count in summary.sentiment_distribution.items():
            percentage = (count / total) * 100
            sentiment_text.append(f"{sentiment}: {percentage:.1f}%")

        # Top entity
        top_entity = summary.top_entities[0]['entity'] if summary.top_entities else "N/A"

        text = f"""Tổng quan phân tích {total} bình luận:

Phân bố cảm xúc:
{', '.join(sentiment_text)}

Thực thể được nhắc đến nhiều nhất: {top_entity}
Số khía cạnh khác nhau: {len(summary.top_aspects)}

Nhìn chung, người xem đang có phản ứng {"tích cực" if summary.sentiment_distribution.get("tích cực", 0) > summary.sentiment_distribution.get("tiêu cực", 0) else "trung lập"} với nội dung.
"""
        return text
