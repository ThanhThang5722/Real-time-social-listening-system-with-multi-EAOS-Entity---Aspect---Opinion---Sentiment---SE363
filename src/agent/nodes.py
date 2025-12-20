"""LangGraph node implementations for agent workflow"""

import json
from typing import Dict, Any
from datetime import datetime
import structlog

from langchain_google_vertexai import ChatVertexAI
from langchain.schema import HumanMessage, SystemMessage

from src.agent.state import AgentState, add_reasoning_trace, add_tool_result, increment_iteration
from src.agent.prompts.system_prompt import (
    SYSTEM_PROMPT,
    UNDERSTAND_PROMPT,
    PLAN_PROMPT,
    OBSERVE_PROMPT,
    SYNTHESIZE_PROMPT,
    RESPOND_PROMPT
)
from src.agent.tools.registry import get_all_tools
from src.config import settings

logger = structlog.get_logger(__name__)


# Initialize Vertex AI LLM
def get_llm():
    """Get Vertex AI Gemini Pro LLM"""
    return ChatVertexAI(
        model_name=settings.vertex_ai_model,
        temperature=settings.vertex_ai_temperature,
        max_output_tokens=settings.vertex_ai_max_output_tokens,
        top_p=settings.vertex_ai_top_p,
        top_k=settings.vertex_ai_top_k,
        project=settings.gcp_project_id,
        location=settings.gcp_location
    )


def understand_node(state: AgentState) -> AgentState:
    """
    Node 1: Understand producer's query and extract intent

    Analyzes the query to determine what the producer is asking for
    and what tools/data will be needed.
    """
    logger.info("Understanding query", query=state['query'])

    try:
        llm = get_llm()

        # Format prompt
        prompt = UNDERSTAND_PROMPT.format(query=state['query'])

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        # Get LLM response
        response = llm.invoke(messages)
        content = response.content

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            understanding = json.loads(json_str)

            # Update state
            state['intent'] = understanding.get('intent', 'status_check')
            state['entities'] = understanding.get('entities', [])
            state['time_frame'] = understanding.get('time_frame', 'current')
            state['urgency'] = understanding.get('urgency', 'medium')

            state = add_reasoning_trace(
                state,
                "understand",
                f"Intent: {state['intent']}, Entities: {state['entities']}, Urgency: {state['urgency']}"
            )

            logger.info(
                "Query understood",
                intent=state['intent'],
                entities=state['entities'],
                urgency=state['urgency']
            )

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM JSON response", error=str(e), response=content)
            # Fallback to simple intent detection
            query_lower = state['query'].lower()

            if any(word in query_lower for word in ['why', 'drop', 'increase', 'problem', 'issue']):
                state['intent'] = 'investigation'
            elif any(word in query_lower for word in ['compare', 'versus', 'vs', 'better']):
                state['intent'] = 'comparison'
            elif any(word in query_lower for word in ['should', 'recommend', 'advice', 'what to']):
                state['intent'] = 'recommendation'
            else:
                state['intent'] = 'status_check'

            state['entities'] = []
            state['time_frame'] = 'current'
            state['urgency'] = 'medium'

    except Exception as e:
        logger.error("Error in understand node", error=str(e))
        state['intent'] = 'status_check'
        state['execution_errors'].append(f"Understand error: {str(e)}")

    return state


def plan_node(state: AgentState) -> AgentState:
    """
    Node 2: Create execution plan based on intent

    Determines which tools to use and in what order.
    """
    logger.info("Planning execution", intent=state['intent'])

    try:
        llm = get_llm()

        # Format prompt
        prompt = PLAN_PROMPT.format(
            intent=state['intent'],
            entities=state['entities'],
            context=state['query']
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)
        content = response.content

        # Parse plan
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            plan = json.loads(json_str)
            state['plan'] = plan
            state['current_step'] = 0

            state = add_reasoning_trace(
                state,
                "plan",
                f"Created plan with {len(plan.get('steps', []))} steps"
            )

            logger.info("Plan created", steps=len(plan.get('steps', [])))

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse plan JSON", error=str(e))
            # Create simple fallback plan
            state['plan'] = create_fallback_plan(state['intent'], state['entities'])

    except Exception as e:
        logger.error("Error in plan node", error=str(e))
        state['plan'] = create_fallback_plan(state['intent'], state['entities'])
        state['execution_errors'].append(f"Plan error: {str(e)}")

    return state


def create_fallback_plan(intent: str, entities: list) -> Dict[str, Any]:
    """Create a simple fallback plan based on intent"""
    if intent == 'status_check':
        tool = 'get_current_eaos' if entities else 'get_trending_topics'
        params = {"program_id": entities[0]} if entities else {"limit": 5, "time_range": "15min"}
    elif intent == 'investigation':
        tool = 'detect_anomalies'
        params = {"program_id": entities[0] if entities else "show", "metric": "eaos"}
    elif intent == 'comparison':
        tool = 'get_comparative_analysis'
        params = {
            "entity_1": entities[0] if len(entities) > 0 else "entity_1",
            "entity_2": entities[1] if len(entities) > 1 else "entity_2"
        }
    else:
        tool = 'get_trending_topics'
        params = {"limit": 5, "time_range": "15min"}

    return {
        "steps": [
            {
                "tool": tool,
                "parameters": params,
                "purpose": f"Execute {intent} query"
            }
        ]
    }


async def execute_node(state: AgentState) -> AgentState:
    """
    Node 3: Execute planned tools

    Runs the tools specified in the plan and collects results.
    """
    logger.info("Executing tools", current_step=state['current_step'])

    try:
        if not state['plan'] or 'steps' not in state['plan']:
            logger.warning("No plan available for execution")
            state['execution_errors'].append("No execution plan available")
            state['should_continue'] = False
            return state

        steps = state['plan']['steps']
        if state['current_step'] >= len(steps):
            logger.info("All steps executed")
            state['should_continue'] = False
            return state

        # Get current step
        step = steps[state['current_step']]
        tool_name = step['tool']
        parameters = step.get('parameters', {})

        logger.info("Executing tool", tool=tool_name, params=parameters)

        # Get tool from registry
        from src.agent.tools.registry import get_all_tools
        tools = {tool.name: tool for tool in get_all_tools()}

        if tool_name not in tools:
            logger.error("Tool not found", tool=tool_name)
            state['execution_errors'].append(f"Tool not found: {tool_name}")
            state['current_step'] += 1
            return state

        tool = tools[tool_name]

        # Execute tool (async)
        try:
            result = await tool.ainvoke(parameters)

            state = add_tool_result(
                state,
                tool_name=tool_name,
                parameters=parameters,
                result=result,
                success=True
            )

            state = add_reasoning_trace(
                state,
                "execute",
                f"Executed {tool_name} successfully"
            )

            logger.info("Tool executed successfully", tool=tool_name)

        except Exception as tool_error:
            logger.error("Tool execution failed", tool=tool_name, error=str(tool_error))
            state['execution_errors'].append(f"Tool {tool_name} failed: {str(tool_error)}")

            state = add_tool_result(
                state,
                tool_name=tool_name,
                parameters=parameters,
                result={"error": str(tool_error)},
                success=False
            )

        # Move to next step
        state['current_step'] += 1

    except Exception as e:
        logger.error("Error in execute node", error=str(e))
        state['execution_errors'].append(f"Execute error: {str(e)}")

    return state


def observe_node(state: AgentState) -> AgentState:
    """
    Node 4: Observe results and decide next action

    Evaluates if we have enough data or need to execute more tools.
    """
    logger.info("Observing results", tool_results=len(state['tool_results']))

    try:
        llm = get_llm()

        # Get latest results
        latest_results = state['tool_results'][-3:] if state['tool_results'] else []

        # Format prompt
        prompt = OBSERVE_PROMPT.format(
            tool_name=latest_results[-1]['tool'] if latest_results else 'none',
            results=json.dumps(latest_results[-1]['result'] if latest_results else {}, indent=2),
            query=state['query']
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)
        content = response.content

        # Parse observation
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            observation = json.loads(json_str)

            state['data_quality'] = observation.get('data_quality', 'partial')
            state['findings'] = observation.get('findings', [])
            state['concerns'] = observation.get('concerns', [])
            state['confidence'] = observation.get('confidence', 0.5)

            next_action = observation.get('next_action', 'synthesize')

            # Decide whether to continue execution
            if next_action == 'continue_execution' and state['current_step'] < len(state['plan']['steps']):
                state['should_continue'] = True
            else:
                state['should_continue'] = False

            state = add_reasoning_trace(
                state,
                "observe",
                f"Data quality: {state['data_quality']}, Confidence: {state['confidence']}, Next: {next_action}"
            )

        except json.JSONDecodeError:
            logger.warning("Failed to parse observation JSON")
            # Simple fallback logic
            if len(state['tool_results']) > 0 and not state['tool_results'][-1]['result'].get('error'):
                state['data_quality'] = 'good'
                state['confidence'] = 0.8
                state['should_continue'] = False
            else:
                state['data_quality'] = 'partial'
                state['confidence'] = 0.5
                state['should_continue'] = state['current_step'] < len(state.get('plan', {}).get('steps', []))

    except Exception as e:
        logger.error("Error in observe node", error=str(e))
        state['should_continue'] = False

    # Increment iteration and check max
    state = increment_iteration(state)

    return state


def synthesize_node(state: AgentState) -> AgentState:
    """
    Node 5: Synthesize results into insights

    Combines all tool results into coherent insights and recommendations.
    """
    logger.info("Synthesizing insights")

    try:
        llm = get_llm()

        # Prepare all results
        all_results = {
            "tool_calls": state['tool_calls'],
            "tool_results": state['tool_results'],
            "findings": state['findings'],
            "concerns": state['concerns']
        }

        prompt = SYNTHESIZE_PROMPT.format(
            query=state['query'],
            all_results=json.dumps(all_results, indent=2, default=str)
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)
        state['insights'] = response.content

        state = add_reasoning_trace(
            state,
            "synthesize",
            "Created insights from all findings"
        )

        logger.info("Insights synthesized")

    except Exception as e:
        logger.error("Error in synthesize node", error=str(e))
        # Create basic synthesis from tool results
        state['insights'] = create_basic_synthesis(state)
        state['execution_errors'].append(f"Synthesize error: {str(e)}")

    return state


def create_basic_synthesis(state: AgentState) -> str:
    """Create basic synthesis if LLM fails"""
    results_summary = []
    for result in state['tool_results']:
        tool = result['tool']
        data = result['result']
        results_summary.append(f"- {tool}: {str(data)[:100]}...")

    return f"Based on {len(state['tool_results'])} tool executions:\n" + "\n".join(results_summary)


def respond_node(state: AgentState) -> AgentState:
    """
    Node 6: Format and return final response

    Creates the final, polished response for the producer.
    """
    logger.info("Formatting response")

    try:
        llm = get_llm()

        prompt = RESPOND_PROMPT.format(
            insights=state['insights'],
            query=state['query']
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)
        state['final_response'] = response.content

        # Calculate processing time
        state['processing_time'] = (datetime.now() - state['timestamp']).total_seconds()

        state = add_reasoning_trace(
            state,
            "respond",
            f"Final response generated in {state['processing_time']:.2f}s"
        )

        logger.info(
            "Response completed",
            processing_time=state['processing_time'],
            iterations=state['iteration_count']
        )

    except Exception as e:
        logger.error("Error in respond node", error=str(e))
        # Fallback to insights as response
        state['final_response'] = state['insights'] or "Unable to generate response."

    return state
