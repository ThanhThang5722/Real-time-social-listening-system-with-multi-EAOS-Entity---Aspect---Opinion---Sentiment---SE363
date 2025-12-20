"""Central registry for all Agent tools"""

from typing import List
from langchain.tools import BaseTool

# Import all tools
from src.agent.tools.eaos_tools import (
    get_current_eaos,
    get_eaos_timeline
)
from src.agent.tools.trend_tools import (
    get_trending_topics,
    get_topic_details
)
from src.agent.tools.search_tools import (
    search_comments,
    get_sample_comments,
    analyze_comment_themes
)
from src.agent.tools.anomaly_tools import (
    detect_anomalies,
    get_program_events
)
from src.agent.tools.recommendation_tools import (
    generate_recommendation,
    get_comparative_analysis
)


# ----------------------------------------
# Tool Collections
# ----------------------------------------

EAOS_TOOLS = [
    get_current_eaos,
    get_eaos_timeline
]

TREND_TOOLS = [
    get_trending_topics,
    get_topic_details
]

SEARCH_TOOLS = [
    search_comments,
    get_sample_comments,
    analyze_comment_themes
]

ANOMALY_TOOLS = [
    detect_anomalies,
    get_program_events
]

RECOMMENDATION_TOOLS = [
    generate_recommendation,
    get_comparative_analysis
]

# All tools for agent
ALL_TOOLS = (
    EAOS_TOOLS +
    TREND_TOOLS +
    SEARCH_TOOLS +
    ANOMALY_TOOLS +
    RECOMMENDATION_TOOLS
)


def get_all_tools() -> List[BaseTool]:
    """Get all available tools for the agent"""
    return ALL_TOOLS


def get_tools_by_category(category: str) -> List[BaseTool]:
    """
    Get tools by category

    Args:
        category: Tool category - "eaos", "trend", "search", "anomaly", "recommendation"

    Returns:
        List of tools in that category
    """
    category_map = {
        "eaos": EAOS_TOOLS,
        "trend": TREND_TOOLS,
        "search": SEARCH_TOOLS,
        "anomaly": ANOMALY_TOOLS,
        "recommendation": RECOMMENDATION_TOOLS
    }

    return category_map.get(category.lower(), [])


def get_tool_descriptions() -> dict:
    """Get descriptions of all available tools"""
    return {
        "eaos_tools": {
            "description": "Tools for querying EAOS scores and timelines",
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in EAOS_TOOLS
            ]
        },
        "trend_tools": {
            "description": "Tools for analyzing trending topics and themes",
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in TREND_TOOLS
            ]
        },
        "search_tools": {
            "description": "Tools for searching and analyzing comments",
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in SEARCH_TOOLS
            ]
        },
        "anomaly_tools": {
            "description": "Tools for detecting anomalies and program events",
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in ANOMALY_TOOLS
            ]
        },
        "recommendation_tools": {
            "description": "Tools for generating recommendations and comparisons",
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description
                }
                for tool in RECOMMENDATION_TOOLS
            ]
        }
    }
