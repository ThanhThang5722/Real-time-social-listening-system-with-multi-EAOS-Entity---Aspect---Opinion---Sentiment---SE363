"""Agent state definition for LangGraph workflow"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator


class AgentState(TypedDict):
    """
    State maintained throughout the agent workflow

    This state is passed through all nodes and updated as the agent progresses.
    """

    # Original query from producer
    query: str

    # Conversation history for context
    messages: Annotated[List[Dict[str, Any]], operator.add]

    # Understanding phase outputs
    intent: Optional[str]  # status_check, investigation, comparison, recommendation
    entities: List[str]  # Entities mentioned in query
    time_frame: Optional[str]  # Time context
    urgency: Optional[str]  # low, medium, high, critical

    # Planning phase outputs
    plan: Optional[Dict[str, Any]]  # Execution plan with steps
    current_step: int  # Current step in plan (default: 0)

    # Execution phase data
    tool_calls: List[Dict[str, Any]]  # History of tool calls
    tool_results: List[Dict[str, Any]]  # Results from tools
    execution_errors: List[str]  # Any errors encountered

    # Observation phase outputs
    data_quality: Optional[str]  # good, partial, insufficient
    findings: List[str]  # Key observations
    concerns: List[str]  # Issues found
    confidence: float  # Confidence in current data (0-1)

    # Synthesis phase outputs
    insights: Optional[str]  # Synthesized insights
    recommendations: List[str]  # Actionable recommendations

    # Final response
    final_response: Optional[str]  # Formatted response for producer

    # Control flow
    should_continue: bool  # Whether to continue execution loop
    max_iterations: int  # Max iterations (default: 5)
    iteration_count: int  # Current iteration (default: 0)

    # Metadata
    timestamp: datetime  # When query was received
    processing_time: float  # Time taken (seconds)

    # Debug info
    reasoning_trace: List[str]  # Reasoning steps for debugging


def create_initial_state(query: str) -> AgentState:
    """
    Create initial agent state from a user query

    Args:
        query: Producer's question or request

    Returns:
        Initial AgentState with defaults
    """
    return AgentState(
        query=query,
        messages=[],
        intent=None,
        entities=[],
        time_frame=None,
        urgency=None,
        plan=None,
        current_step=0,
        tool_calls=[],
        tool_results=[],
        execution_errors=[],
        data_quality=None,
        findings=[],
        concerns=[],
        confidence=0.0,
        insights=None,
        recommendations=[],
        final_response=None,
        should_continue=True,
        max_iterations=5,
        iteration_count=0,
        timestamp=datetime.now(),
        processing_time=0.0,
        reasoning_trace=[]
    )


def add_reasoning_trace(state: AgentState, step: str, description: str) -> AgentState:
    """
    Add reasoning step to trace for debugging

    Args:
        state: Current agent state
        step: Step name (e.g., "understand", "plan")
        description: What happened in this step

    Returns:
        Updated state
    """
    trace_entry = f"[{step}] {description}"
    state['reasoning_trace'].append(trace_entry)
    return state


def add_tool_result(
    state: AgentState,
    tool_name: str,
    parameters: Dict[str, Any],
    result: Dict[str, Any],
    success: bool = True
) -> AgentState:
    """
    Record a tool execution and its result

    Args:
        state: Current agent state
        tool_name: Name of tool executed
        parameters: Parameters passed to tool
        result: Tool execution result
        success: Whether tool execution succeeded

    Returns:
        Updated state
    """
    tool_call = {
        "tool": tool_name,
        "parameters": parameters,
        "timestamp": datetime.now(),
        "success": success
    }
    state['tool_calls'].append(tool_call)

    tool_result = {
        "tool": tool_name,
        "result": result,
        "timestamp": datetime.now()
    }
    state['tool_results'].append(tool_result)

    return state


def increment_iteration(state: AgentState) -> AgentState:
    """Increment iteration counter and check max iterations"""
    state['iteration_count'] += 1

    if state['iteration_count'] >= state['max_iterations']:
        state['should_continue'] = False
        state['reasoning_trace'].append(
            f"[control] Max iterations ({state['max_iterations']}) reached"
        )

    return state
