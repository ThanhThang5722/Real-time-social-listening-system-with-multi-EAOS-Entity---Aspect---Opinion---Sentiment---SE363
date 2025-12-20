"""Pydantic schemas for Agent Tool inputs and outputs"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ----------------------------------------
# Enums
# ----------------------------------------

class Granularity(str, Enum):
    """Time granularity for timeline queries"""
    MINUTE = "minute"
    FIVE_MIN = "5min"
    SEGMENT = "segment"


class TimeRange(str, Enum):
    """Predefined time ranges for queries"""
    FIVE_MIN = "5min"
    FIFTEEN_MIN = "15min"
    ONE_HOUR = "1hour"


class MetricType(str, Enum):
    """Metric types for anomaly detection"""
    EAOS = "eaos"
    VOLUME = "volume"
    SENTIMENT = "sentiment"


class TrendDirection(str, Enum):
    """Trend direction indicators"""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    SPIKE = "spike"


class Severity(str, Enum):
    """Anomaly severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ----------------------------------------
# Tool Input Schemas
# ----------------------------------------

class GetCurrentEAOSInput(BaseModel):
    """Input for get_current_eaos tool"""
    program_id: str = Field(
        description="Program/entity identifier to get EAOS score for"
    )


class GetEAOSTimelineInput(BaseModel):
    """Input for get_eaos_timeline tool"""
    program_id: str = Field(description="Program/entity identifier")
    from_time: datetime = Field(description="Start time for timeline")
    to_time: datetime = Field(description="End time for timeline")
    granularity: Granularity = Field(
        default=Granularity.FIVE_MIN,
        description="Time granularity: minute, 5min, or segment"
    )


class GetTrendingTopicsInput(BaseModel):
    """Input for get_trending_topics tool"""
    limit: int = Field(default=10, ge=1, le=50, description="Max topics to return")
    time_range: TimeRange = Field(
        default=TimeRange.FIFTEEN_MIN,
        description="Time range: 5min, 15min, or 1hour"
    )


class SearchCommentsInput(BaseModel):
    """Input for search_comments tool"""
    query: str = Field(description="Search query text")
    time_range: Optional[TimeRange] = Field(
        default=None,
        description="Optional time range filter"
    )
    sentiment_filter: Optional[str] = Field(
        default=None,
        description="Optional sentiment filter: positive, negative, or neutral"
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results")


class DetectAnomaliesInput(BaseModel):
    """Input for detect_anomalies tool"""
    program_id: str = Field(description="Program/entity identifier")
    metric: MetricType = Field(
        default=MetricType.EAOS,
        description="Metric to check: eaos, volume, or sentiment"
    )


class GetProgramEventsInput(BaseModel):
    """Input for get_program_events tool"""
    program_id: str = Field(description="Program/entity identifier")
    time: datetime = Field(description="Time to get events around")


class GenerateRecommendationInput(BaseModel):
    """Input for generate_recommendation tool"""
    context: str = Field(
        description="Summary of findings and current situation"
    )


# ----------------------------------------
# Tool Output Schemas
# ----------------------------------------

class EAOSScoreOutput(BaseModel):
    """Output for get_current_eaos"""
    score: float = Field(description="Current EAOS score (0-1)")
    positive_pct: float = Field(description="Percentage of positive comments")
    negative_pct: float = Field(description="Percentage of negative comments")
    total_comments: int = Field(description="Total comment count")
    timestamp: datetime = Field(description="Score calculation timestamp")


class EAOSTimelinePoint(BaseModel):
    """Single point in EAOS timeline"""
    timestamp: datetime
    score: float
    comment_count: int


class EAOSTimelineOutput(BaseModel):
    """Output for get_eaos_timeline"""
    timeline: List[EAOSTimelinePoint]
    program_id: str
    granularity: str


class TrendingTopic(BaseModel):
    """Single trending topic"""
    topic: str
    count: int
    sentiment: float
    trend_direction: TrendDirection


class TrendingTopicsOutput(BaseModel):
    """Output for get_trending_topics"""
    topics: List[TrendingTopic]
    time_range: str
    timestamp: datetime


class CommentResult(BaseModel):
    """Single comment search result"""
    text: str
    timestamp: datetime
    sentiment: str
    engagement_score: float
    username: Optional[str] = None


class SearchCommentsOutput(BaseModel):
    """Output for search_comments"""
    comments: List[CommentResult]
    query: str
    total_found: int


class Anomaly(BaseModel):
    """Single anomaly detection result"""
    timestamp: datetime
    metric_value: float
    expected_value: float
    deviation_pct: float
    severity: Severity


class DetectAnomaliesOutput(BaseModel):
    """Output for detect_anomalies"""
    anomalies: List[Anomaly]
    program_id: str
    metric: str


class ProgramEvent(BaseModel):
    """Single program event"""
    timestamp: datetime
    event_type: str
    description: str


class ProgramEventsOutput(BaseModel):
    """Output for get_program_events"""
    events: List[ProgramEvent]
    program_id: str


class Recommendation(BaseModel):
    """Output for generate_recommendation"""
    recommendation: str
    confidence: float
    reasoning: str
