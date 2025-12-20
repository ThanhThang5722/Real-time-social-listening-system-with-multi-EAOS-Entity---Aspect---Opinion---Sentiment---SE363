"""LangFuse integration for LLM observability"""

from typing import Optional, Dict, Any
from functools import wraps
import structlog

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context
from src.config import settings

logger = structlog.get_logger(__name__)


class LangFuseMonitor:
    """
    LangFuse monitoring integration

    Tracks:
    - LLM calls (Vertex AI Gemini)
    - Agent tool executions
    - Reasoning steps
    - Costs and latency
    """

    def __init__(self):
        self.client: Optional[Langfuse] = None
        self.enabled = settings.langfuse_enabled

    def initialize(self):
        """Initialize LangFuse client"""
        if not self.enabled:
            logger.info("LangFuse monitoring disabled")
            return

        try:
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host
            )

            # Test connection
            self.client.auth_check()

            logger.info(
                "LangFuse initialized successfully",
                host=settings.langfuse_host
            )

        except Exception as e:
            logger.error("Failed to initialize LangFuse", error=str(e))
            self.enabled = False

    def trace_agent_query(
        self,
        query: str,
        program_id: str,
        session_id: Optional[str] = None
    ):
        """
        Create trace for agent query

        Returns trace context manager
        """
        if not self.enabled or not self.client:
            return NullContext()

        try:
            trace = self.client.trace(
                name="agent_query",
                user_id=program_id,
                session_id=session_id,
                input={"query": query, "program_id": program_id},
                metadata={
                    "system": "tv_producer_analytics",
                    "version": "1.0.0"
                }
            )
            return trace

        except Exception as e:
            logger.warning("Failed to create trace", error=str(e))
            return NullContext()

    def log_llm_call(
        self,
        model: str,
        prompt: str,
        response: str,
        metadata: Optional[Dict] = None
    ):
        """Log LLM API call"""
        if not self.enabled or not self.client:
            return

        try:
            self.client.generation(
                name="vertex_ai_gemini",
                model=model,
                model_parameters={
                    "temperature": settings.vertex_ai_temperature,
                    "max_tokens": settings.vertex_ai_max_output_tokens
                },
                input=prompt,
                output=response,
                metadata=metadata or {}
            )

        except Exception as e:
            logger.warning("Failed to log LLM call", error=str(e))

    def log_tool_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        duration_ms: float,
        success: bool = True
    ):
        """Log agent tool execution"""
        if not self.enabled or not self.client:
            return

        try:
            self.client.span(
                name=f"tool_{tool_name}",
                input=parameters,
                output=result,
                metadata={
                    "tool": tool_name,
                    "duration_ms": duration_ms,
                    "success": success
                }
            )

        except Exception as e:
            logger.warning("Failed to log tool execution", error=str(e))

    def log_reasoning_step(
        self,
        step_name: str,
        input_data: Any,
        output_data: Any,
        metadata: Optional[Dict] = None
    ):
        """Log agent reasoning step"""
        if not self.enabled or not self.client:
            return

        try:
            self.client.span(
                name=f"reasoning_{step_name}",
                input=input_data,
                output=output_data,
                metadata=metadata or {}
            )

        except Exception as e:
            logger.warning("Failed to log reasoning step", error=str(e))

    def flush(self):
        """Flush pending traces"""
        if self.enabled and self.client:
            try:
                self.client.flush()
            except Exception as e:
                logger.warning("Failed to flush traces", error=str(e))

    def shutdown(self):
        """Shutdown LangFuse client"""
        if self.enabled and self.client:
            try:
                self.client.flush()
                logger.info("LangFuse shutdown successfully")
            except Exception as e:
                logger.error("Error during LangFuse shutdown", error=str(e))


class NullContext:
    """Null context manager when LangFuse is disabled"""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def update(self, **kwargs):
        pass


# Global monitor instance
langfuse_monitor = LangFuseMonitor()


def traced_agent_function(name: str):
    """
    Decorator to trace agent functions with LangFuse

    Usage:
        @traced_agent_function("understand_query")
        async def understand_node(state):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not langfuse_monitor.enabled:
                return await func(*args, **kwargs)

            try:
                # Start span
                import time
                start = time.time()

                # Execute function
                result = await func(*args, **kwargs)

                # Log span
                duration = (time.time() - start) * 1000  # ms
                langfuse_monitor.log_reasoning_step(
                    step_name=name,
                    input_data={"args": str(args)[:100], "kwargs": str(kwargs)[:100]},
                    output_data={"result": str(result)[:100]},
                    metadata={"duration_ms": duration}
                )

                return result

            except Exception as e:
                logger.error(f"Error in traced function {name}", error=str(e))
                raise

        return wrapper
    return decorator
