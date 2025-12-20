from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class EAOSLabel(BaseModel):
    """Single EAOS (Entity-Aspect-Opinion-Sentiment) label"""
    entity: str
    aspect: str
    opinion: str
    sentiment: str  # "tích cực", "tiêu cực", "trung lập"


class Comment(BaseModel):
    """Comment with EAOS analysis"""
    id: Optional[str] = None
    text: str
    labels: List[EAOSLabel]
    timestamp: Optional[datetime] = None
    username: Optional[str] = None


class CommentStream(BaseModel):
    """Streaming comment data"""
    comment: Comment
    stream_id: str


class ChatMessage(BaseModel):
    """Chat message for chatbot"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    """Chat request from user"""
    message: str
    context: Optional[str] = None


class AnalyticsSummary(BaseModel):
    """Summary statistics for dashboard"""
    total_comments: int
    sentiment_distribution: dict  # {"tích cực": 100, "tiêu cực": 20, "trung lập": 50}
    top_entities: List[dict]  # [{"entity": "chương trình", "count": 50}, ...]
    top_aspects: List[dict]
    recent_comments: List[Comment]
