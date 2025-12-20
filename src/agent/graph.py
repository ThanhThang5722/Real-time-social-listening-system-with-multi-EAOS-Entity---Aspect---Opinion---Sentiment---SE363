"""LangGraph workflow construction"""

from langgraph.graph import StateGraph, END
import structlog

from src.agent.state import AgentState
from src.agent.nodes import (
    understand_node,
    plan_node,
    execute_node,
    observe_node,
    synthesize_node,
    respond_node
)

logger = structlog.get_logger(__name__)


def should_continue_execution(state: AgentState) -> str:
    """
    Conditional edge: Decide whether to continue execution or move to synthesis

    Returns:
        "execute" if should continue, "synthesize" otherwise
    """
    # Check if we should continue
    if state['should_continue'] and state['iteration_count'] < state['max_iterations']:
        # Check if there are more steps in plan
        if state['plan'] and state['current_step'] < len(state['plan'].get('steps', [])):
            logger.debug("Continuing execution", current_step=state['current_step'])
            return "execute"

    logger.debug("Moving to synthesis", iteration=state['iteration_count'])
    return "synthesize"


def create_agent_graph() -> StateGraph:
    """
    Create the agent workflow graph

    Workflow:
    START → understand → plan → execute → observe → [conditional]
                                            ↓           ↓
                                            ↓ (if continue)
                                            ↓           ↓
                                         execute ←─────┘
                                            ↓
                                         observe (if done)
                                            ↓
                                       synthesize
                                            ↓
                                         respond
                                            ↓
                                          END
    """
    # Create graph with AgentState
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("understand", understand_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("observe", observe_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("respond", respond_node)

    # Add edges
    # Linear flow: understand → plan → execute → observe
    workflow.add_edge("understand", "plan")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "observe")

    # Conditional edge: observe → execute (loop) OR synthesize
    workflow.add_conditional_edges(
        "observe",
        should_continue_execution,
        {
            "execute": "execute",
            "synthesize": "synthesize"
        }
    )

    # Final flow: synthesize → respond → END
    workflow.add_edge("synthesize", "respond")
    workflow.add_edge("respond", END)

    # Set entry point
    workflow.set_entry_point("understand")

    return workflow


def compile_agent_graph():
    """
    Compile the agent graph for execution

    Returns:
        Compiled graph ready for invocation
    """
    workflow = create_agent_graph()
    compiled = workflow.compile()

    logger.info("Agent graph compiled successfully")
    return compiled


# Create compiled graph instance
agent_graph = compile_agent_graph()
