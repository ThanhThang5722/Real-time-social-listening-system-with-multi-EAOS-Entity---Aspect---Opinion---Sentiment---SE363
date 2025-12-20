"""Pydantic schemas for API requests and responses"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ----------------------------------------
# Request Schemas
# ----------------------------------------

class ChatRequest(BaseModel):
    """Chat request to agent"""
    message: str = Field(..., min_length=1, max_length=1000, description="Producer's question")
    program_id: str = Field(..., description="Program identifier")
    session_id: Optional[str] = Field(None, description="Optional session ID for context")
    verbose: bool = Field(False, description="Include reasoning steps in response")


class EAOSTimelineRequest(BaseModel):
    """EAOS timeline query parameters"""
    from_time: datetime = Field(..., description="Start time")
    to_time: datetime = Field(..., description="End time")
    granularity: str = Field("5min", description="Time granularity: minute, 5min, segment")


# ----------------------------------------
# Response Schemas
# ----------------------------------------

class SourceReference(BaseModel):
    """Source data reference"""
    tool: str = Field(..., description="Tool that provided this data")
    data: Dict[str, Any] = Field(..., description="Source data")
    timestamp: datetime = Field(..., description="When data was retrieved")


class ReasoningStep(BaseModel):
    """Single reasoning step"""
    step: str = Field(..., description="Step name")
    description: str = Field(..., description="What happened")
    duration_ms: Optional[float] = Field(None, description="Step duration in milliseconds")


class ChatResponse(BaseModel):
    """Chat response from agent"""
    response: str = Field(..., description="Agent's response")
    program_id: str = Field(..., description="Program identifier")
    sources: List[SourceReference] = Field(default_factory=list, description="Data sources used")
    reasoning_steps: Optional[List[ReasoningStep]] = Field(None, description="Reasoning trace (if verbose)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class EAOSCurrent(BaseModel):
    """Current EAOS data"""
    program_id: str
    score: float = Field(..., ge=0, le=1, description="EAOS score (0-1)")
    positive: int = Field(..., ge=0, description="Positive comment count")
    negative: int = Field(..., ge=0, description="Negative comment count")
    neutral: int = Field(..., ge=0, description="Neutral comment count")
    total: int = Field(..., ge=0, description="Total comment count")
    updated_at: datetime = Field(..., description="Last update timestamp")


class EAOSTimelinePoint(BaseModel):
    """Single point in EAOS timeline"""
    timestamp: datetime
    score: float
    positive_count: int
    negative_count: int
    neutral_count: int
    total_comments: int


class EAOSTimelineResponse(BaseModel):
    """EAOS timeline data"""
    program_id: str
    timeline: List[EAOSTimelinePoint]
    granularity: str
    from_time: datetime
    to_time: datetime


class TrendingTopic(BaseModel):
    """Single trending topic"""
    topic: str
    score: float = Field(..., description="Trending score (mentions)")
    rank: int = Field(..., description="Rank position")


class TrendsResponse(BaseModel):
    """Trending topics response"""
    trends: List[TrendingTopic]
    time_range: str
    timestamp: datetime


class HealthStatus(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Overall status: healthy, degraded, unhealthy")
    timestamp: datetime
    services: Dict[str, str] = Field(..., description="Status of each service")
    version: str = Field(..., description="API version")


class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.now)
