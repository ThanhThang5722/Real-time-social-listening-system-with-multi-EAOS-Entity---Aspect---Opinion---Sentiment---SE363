"""Agent tools for generating recommendations"""

import asyncio
from typing import Dict, Any
from langchain.tools import tool
import structlog

logger = structlog.get_logger(__name__)


@tool
def generate_recommendation(context: str) -> Dict[str, Any]:
    """
    Generate actionable recommendations based on analysis context.

    Takes the current situation summary and provides specific, actionable
    recommendations for the producer. Uses rule-based logic and patterns.

    Args:
        context: Summary of findings and current situation

    Returns:
        Dictionary with:
        - recommendation: Specific actionable recommendation
        - confidence: Confidence score (0-1)
        - reasoning: Explanation of why this recommendation

    Example:
        >>> context = "EAOS for contestant_1 dropped 40% in last 5 minutes. Negative comments mention 'unfair scoring'."
        >>> result = generate_recommendation(context)
        >>> print(result['recommendation'])

    Note:
        This is a rule-based implementation. In production, could be
        enhanced with ML models or LLM-based generation.
    """
    try:
        logger.info("Generating recommendation", context_length=len(context))

        context_lower = context.lower()

        # Rule-based recommendations
        recommendations = []

        # EAOS drops
        if "eaos" in context_lower and ("drop" in context_lower or "decrease" in context_lower):
            if "negative" in context_lower:
                recommendations.append({
                    "recommendation": "Investigate negative feedback immediately. Review recent comments to identify specific issues. Consider addressing concerns in next segment.",
                    "confidence": 0.85,
                    "reasoning": "Significant EAOS drop with negative sentiment indicates viewer dissatisfaction that needs immediate attention."
                })
            else:
                recommendations.append({
                    "recommendation": "Monitor EAOS trend closely. Prepare to pivot content if decline continues. Check for technical issues (audio/video quality).",
                    "confidence": 0.75,
                    "reasoning": "EAOS decline detected but cause unclear. Proactive monitoring recommended."
                })

        # Volume spikes
        if "volume" in context_lower and "spike" in context_lower:
            recommendations.append({
                "recommendation": "High engagement detected. Extend or repeat this segment type. Capitalize on increased attention.",
                "confidence": 0.80,
                "reasoning": "Sudden volume increase indicates high viewer interest. Opportunity to maximize engagement."
            })

        # Sentiment issues
        if "negative" in context_lower and ("complaint" in context_lower or "issue" in context_lower):
            recommendations.append({
                "recommendation": "Address viewer concerns directly. Consider on-air acknowledgment or social media response. Document feedback for post-show review.",
                "confidence": 0.82,
                "reasoning": "Multiple negative comments about specific issues require acknowledgment and resolution."
            })

        # Trending topics
        if "trend" in context_lower or "popular" in context_lower:
            recommendations.append({
                "recommendation": "Leverage trending topic momentum. Feature this content more prominently. Prepare related content for next segment.",
                "confidence": 0.78,
                "reasoning": "Trending topics indicate strong viewer interest. Amplifying this content can boost engagement."
            })

        # Technical issues
        if any(word in context_lower for word in ["audio", "sound", "video", "quality", "technical"]):
            recommendations.append({
                "recommendation": "Check technical setup immediately. Verify audio/video quality. Consider brief pause to fix if issues confirmed.",
                "confidence": 0.90,
                "reasoning": "Technical issues directly impact viewer experience and can quickly lose audience. Immediate action critical."
            })

        # Anomalies
        if "anomaly" in context_lower or "unusual" in context_lower:
            recommendations.append({
                "recommendation": "Investigate anomaly cause. Compare with typical patterns. Check for external factors (competing content, technical issues).",
                "confidence": 0.70,
                "reasoning": "Unusual patterns detected. Understanding root cause important for appropriate response."
            })

        # Default recommendation if no specific patterns matched
        if not recommendations:
            recommendations.append({
                "recommendation": "Continue monitoring metrics. Current situation appears stable. Maintain current content strategy.",
                "confidence": 0.60,
                "reasoning": "No significant issues detected. Standard monitoring recommended."
            })

        # Return highest confidence recommendation
        best_recommendation = max(recommendations, key=lambda x: x['confidence'])

        return best_recommendation

    except Exception as e:
        logger.error("Failed to generate recommendation", error=str(e))
        return {
            "recommendation": "Unable to generate recommendation. Please review metrics manually.",
            "confidence": 0.0,
            "reasoning": f"Error: {str(e)}",
            "error": str(e)
        }


@tool
async def get_comparative_analysis(
    entity_1: str,
    entity_2: str,
    time_range: str = "15min"
) -> Dict[str, Any]:
    """
    Compare metrics between two entities (contestants, segments, etc.).

    Provides comparative analysis to understand relative performance.
    Useful for decisions about content focus or resource allocation.

    Args:
        entity_1: First entity identifier
        entity_2: Second entity identifier
        time_range: Time range - "5min", "15min", or "1hour"

    Returns:
        Comparative analysis with recommendations

    Example:
        >>> result = await get_comparative_analysis("contestant_1", "contestant_2")
        >>> print(result['comparison_summary'])
    """
    try:
        logger.info(
            "Performing comparative analysis",
            entity_1=entity_1,
            entity_2=entity_2
        )

        from src.agent.tools.eaos_tools import get_current_eaos

        # Get EAOS for both entities
        eaos_1 = await get_current_eaos(entity_1)
        eaos_2 = await get_current_eaos(entity_2)

        score_1 = eaos_1.get('score', 0)
        score_2 = eaos_2.get('score', 0)

        # Calculate difference
        diff = score_1 - score_2
        diff_pct = (diff / score_2 * 100) if score_2 != 0 else 0

        # Determine winner
        if abs(diff_pct) < 5:
            comparison = "roughly equal"
            winner = "tie"
        elif diff > 0:
            comparison = "significantly better"
            winner = entity_1
        else:
            comparison = "significantly worse"
            winner = entity_2

        # Generate comparative summary
        summary = f"{entity_1} is performing {comparison} than {entity_2} (EAOS: {score_1:.2f} vs {score_2:.2f}, {abs(diff_pct):.1f}% difference)"

        # Recommendation
        if winner == "tie":
            recommendation = f"Both {entity_1} and {entity_2} are performing similarly. Consider featuring both equally."
        else:
            recommendation = f"Consider giving more screen time to {winner}, which is resonating better with viewers."

        return {
            "entity_1": {
                "name": entity_1,
                "eaos_score": score_1,
                "comments": eaos_1.get('total_comments', 0)
            },
            "entity_2": {
                "name": entity_2,
                "eaos_score": score_2,
                "comments": eaos_2.get('total_comments', 0)
            },
            "difference": {
                "absolute": round(diff, 4),
                "percentage": round(diff_pct, 2)
            },
            "winner": winner,
            "comparison_summary": summary,
            "recommendation": recommendation
        }

    except Exception as e:
        logger.error("Failed comparative analysis", error=str(e))
        return {
            "error": str(e)
        }
