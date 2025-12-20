"""Agent orchestrator - Main entry point for agent queries"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import structlog

from src.agent.state import create_initial_state, AgentState
from src.agent.graph import agent_graph
from src.storage.redis_client import redis_client
from src.storage.clickhouse_client import clickhouse_client
from src.storage.elasticsearch_client import elasticsearch_client

logger = structlog.get_logger(__name__)


class AgentOrchestrator:
    """
    Main orchestrator for TV Producer Analytics Agent

    Handles query processing, state management, and database connections.
    """

    def __init__(self):
        self.connections_initialized = False

    async def initialize_connections(self):
        """Initialize database connections if not already done"""
        if not self.connections_initialized:
            try:
                await redis_client.connect()
                clickhouse_client.connect()
                await elasticsearch_client.connect()

                self.connections_initialized = True
                logger.info("Agent connections initialized")

            except Exception as e:
                logger.error("Failed to initialize connections", error=str(e))
                raise

    async def process_query(
        self,
        query: str,
        max_iterations: int = 5,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Process a producer query through the agent workflow

        Args:
            query: Producer's question or request
            max_iterations: Maximum tool execution iterations
            verbose: Include debug info in response

        Returns:
            Dictionary with response and metadata
        """
        start_time = datetime.now()

        try:
            # Ensure connections are ready
            await self.initialize_connections()

            # Create initial state
            state = create_initial_state(query)
            state['max_iterations'] = max_iterations

            logger.info("Processing query", query=query)

            # Run through agent graph
            final_state = await agent_graph.ainvoke(state)

            # Calculate metrics
            processing_time = (datetime.now() - start_time).total_seconds()

            # Format response
            response = {
                "success": True,
                "response": final_state.get('final_response', 'No response generated'),
                "metadata": {
                    "query": query,
                    "intent": final_state.get('intent'),
                    "entities": final_state.get('entities'),
                    "urgency": final_state.get('urgency'),
                    "confidence": final_state.get('confidence', 0.0),
                    "iterations": final_state.get('iteration_count'),
                    "tools_used": [call['tool'] for call in final_state.get('tool_calls', [])],
                    "processing_time_seconds": processing_time,
                    "timestamp": start_time.isoformat()
                }
            }

            # Add debug info if verbose
            if verbose:
                response['debug'] = {
                    "reasoning_trace": final_state.get('reasoning_trace', []),
                    "tool_results": final_state.get('tool_results', []),
                    "findings": final_state.get('findings', []),
                    "concerns": final_state.get('concerns', []),
                    "errors": final_state.get('execution_errors', [])
                }

            logger.info(
                "Query processed successfully",
                query=query,
                intent=final_state.get('intent'),
                processing_time=processing_time,
                iterations=final_state.get('iteration_count')
            )

            return response

        except Exception as e:
            logger.error("Error processing query", query=query, error=str(e))

            return {
                "success": False,
                "response": f"Error processing query: {str(e)}",
                "error": str(e),
                "metadata": {
                    "query": query,
                    "processing_time_seconds": (datetime.now() - start_time).total_seconds()
                }
            }

    async def close(self):
        """Close database connections"""
        try:
            await redis_client.disconnect()
            clickhouse_client.disconnect()
            await elasticsearch_client.disconnect()

            self.connections_initialized = False
            logger.info("Agent connections closed")

        except Exception as e:
            logger.error("Error closing connections", error=str(e))


# Global orchestrator instance
orchestrator = AgentOrchestrator()


async def query_agent(
    query: str,
    max_iterations: int = 5,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to query the agent

    Args:
        query: Producer's question
        max_iterations: Max tool iterations
        verbose: Include debug info

    Returns:
        Agent response dictionary

    Example:
        >>> response = await query_agent("How is contestant 1 doing?")
        >>> print(response['response'])
    """
    return await orchestrator.process_query(
        query=query,
        max_iterations=max_iterations,
        verbose=verbose
    )
