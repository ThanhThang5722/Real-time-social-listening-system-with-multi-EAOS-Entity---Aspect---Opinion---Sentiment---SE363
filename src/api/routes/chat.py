"""Chat endpoint for agent interaction"""

from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
import uuid
import structlog

from src.api.schemas import ChatRequest, ChatResponse, ErrorResponse, SourceReference, ReasoningStep
from src.api.dependencies import with_retry, rate_limiter
from src.agent.orchestrator import orchestrator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, responses={429: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
@with_retry(max_retries=2, delay=1.0)
async def chat_with_agent(request: ChatRequest, http_request: Request):
    """
    Chat with AI Agent to analyze comments and get insights

    This endpoint processes natural language queries from TV producers
    and returns actionable insights using AI reasoning.

    **Example queries:**
    - "EAOS hiện tại của chương trình là bao nhiêu?"
    - "Top 5 chủ đề đang hot nhất?"
    - "Tại sao sentiment giảm mạnh ở phút 25?"
    - "Thí sinh nào đang được yêu thích nhất?"

    **Rate limit:** 60 requests per minute per IP
    """
    request_id = str(uuid.uuid4())
    start_time = datetime.now()

    try:
        # Rate limiting
        client_ip = http_request.client.host
        if not await rate_limiter.check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )

        logger.info(
            "Chat request received",
            request_id=request_id,
            program_id=request.program_id,
            message=request.message[:50]
        )

        # Build query with program context
        contextualized_query = f"[Program: {request.program_id}] {request.message}"

        # Query agent
        agent_response = await orchestrator.process_query(
            query=contextualized_query,
            max_iterations=5,
            verbose=request.verbose
        )

        if not agent_response.get('success'):
            raise HTTPException(
                status_code=500,
                detail=f"Agent processing failed: {agent_response.get('error', 'Unknown error')}"
            )

        # Format sources
        sources = []
        if agent_response.get('metadata', {}).get('tools_used'):
            for tool in agent_response['metadata']['tools_used']:
                sources.append(SourceReference(
                    tool=tool,
                    data={},  # Could be populated from tool_results
                    timestamp=datetime.now()
                ))

        # Format reasoning steps if verbose
        reasoning_steps = None
        if request.verbose and agent_response.get('debug', {}).get('reasoning_trace'):
            reasoning_steps = []
            for trace in agent_response['debug']['reasoning_trace']:
                # Parse trace: "[step] description"
                if ']' in trace:
                    step_name = trace.split(']')[0].replace('[', '').strip()
                    description = trace.split(']', 1)[1].strip()
                    reasoning_steps.append(ReasoningStep(
                        step=step_name,
                        description=description
                    ))

        processing_time = (datetime.now() - start_time).total_seconds()

        logger.info(
            "Chat request completed",
            request_id=request_id,
            program_id=request.program_id,
            processing_time=processing_time,
            success=True
        )

        return ChatResponse(
            response=agent_response['response'],
            program_id=request.program_id,
            sources=sources,
            reasoning_steps=reasoning_steps,
            metadata={
                "request_id": request_id,
                "processing_time_seconds": processing_time,
                "intent": agent_response.get('metadata', {}).get('intent'),
                "confidence": agent_response.get('metadata', {}).get('confidence', 0.0),
                "session_id": request.session_id
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Chat request failed",
            request_id=request_id,
            program_id=request.program_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
