"""Few-shot examples for agent reasoning"""

EXAMPLE_STATUS_CHECK = {
    "query": "How is contestant 1 performing?",
    "intent": {
        "intent": "status_check",
        "entities": ["contestant_1"],
        "time_frame": "current",
        "urgency": "medium",
        "required_tools": ["get_current_eaos", "get_trending_topics"],
        "reasoning": "Producer wants current performance metrics for a specific contestant"
    },
    "plan": {
        "steps": [
            {
                "tool": "get_current_eaos",
                "parameters": {"program_id": "contestant_1"},
                "purpose": "Get current EAOS score and sentiment breakdown",
                "next_if_success": "synthesize",
                "next_if_fail": "search_comments"
            }
        ],
        "expected_outcomes": ["EAOS score", "sentiment distribution"],
        "fallback_plan": "If no EAOS data, search recent comments"
    },
    "response": """Contestant 1 is performing well with an EAOS of 0.82/1.0.

**Details:**
- 68% positive comments, 12% negative
- Based on 142 comments in last 5 minutes
- Slightly above show average

**Recommendation:** Continue current coverage. Audience engagement is strong."""
}


EXAMPLE_INVESTIGATION = {
    "query": "Why did EAOS drop suddenly at 7:45 PM?",
    "intent": {
        "intent": "investigation",
        "entities": [],
        "time_frame": "specific_time",
        "urgency": "high",
        "required_tools": ["detect_anomalies", "get_program_events", "search_comments"],
        "reasoning": "Producer noticed a problem and needs root cause analysis"
    },
    "plan": {
        "steps": [
            {
                "tool": "detect_anomalies",
                "parameters": {"program_id": "show", "metric": "eaos"},
                "purpose": "Confirm the anomaly and get details",
                "next_if_success": "search_comments",
                "next_if_fail": "get_eaos_timeline"
            },
            {
                "tool": "search_comments",
                "parameters": {
                    "query": "",
                    "time_range": "5min",
                    "sentiment_filter": "negative",
                    "limit": 20
                },
                "purpose": "Find what viewers were complaining about",
                "next_if_success": "generate_recommendation",
                "next_if_fail": "get_program_events"
            }
        ],
        "expected_outcomes": ["Root cause identification", "Specific viewer complaints"],
        "fallback_plan": "Check program events for technical issues"
    },
    "response": """⚠️ EAOS dropped 35% at 7:45 PM due to audio issues.

**Root Cause:**
- 47 negative comments about "sound quality" and "can't hear"
- Audio level dropped significantly during that segment
- Anomaly severity: HIGH

**Recommendation:**
🔴 URGENT: Check audio mixer settings immediately. Consider brief on-air acknowledgment if issue persists."""
}


EXAMPLE_COMPARISON = {
    "query": "Should I give more screen time to contestant A or B?",
    "intent": {
        "intent": "comparison",
        "entities": ["contestant_A", "contestant_B"],
        "time_frame": "current",
        "urgency": "medium",
        "required_tools": ["get_comparative_analysis"],
        "reasoning": "Producer needs data-driven decision between two options"
    },
    "plan": {
        "steps": [
            {
                "tool": "get_comparative_analysis",
                "parameters": {
                    "entity_1": "contestant_A",
                    "entity_2": "contestant_B",
                    "time_range": "15min"
                },
                "purpose": "Compare audience reception of both contestants",
                "next_if_success": "synthesize",
                "next_if_fail": "get_current_eaos"
            }
        ],
        "expected_outcomes": ["Clear winner based on EAOS", "Recommendation"],
        "fallback_plan": "Get individual EAOS scores if comparison fails"
    },
    "response": """Give more screen time to Contestant B.

**Comparison:**
- Contestant A: EAOS 0.64 (195 comments)
- Contestant B: EAOS 0.79 (312 comments) ✓
- Difference: +23% higher engagement

**Reasoning:** Contestant B is generating significantly more positive engagement and comment volume. Viewers are more invested in their story.

**Action:** Increase B's screen time by 20-30% in next segment."""
}


EXAMPLE_TRENDING = {
    "query": "What's trending right now?",
    "intent": {
        "intent": "status_check",
        "entities": [],
        "time_frame": "current",
        "urgency": "low",
        "required_tools": ["get_trending_topics"],
        "reasoning": "Producer wants to know what's capturing audience attention"
    },
    "plan": {
        "steps": [
            {
                "tool": "get_trending_topics",
                "parameters": {"limit": 5, "time_range": "15min"},
                "purpose": "Get top trending topics",
                "next_if_success": "synthesize",
                "next_if_fail": "fallback"
            }
        ],
        "expected_outcomes": ["List of trending topics with sentiment"],
        "fallback_plan": "Search most common entities in recent comments"
    },
    "response": """Top 5 Trending Topics (last 15 min):

1. **"final performance"** - 234 mentions, positive (↗️ rising)
2. **"judges' decision"** - 189 mentions, mixed (🔥 spike)
3. **"contestant_A"** - 167 mentions, positive (↗️ rising)
4. **"elimination"** - 143 mentions, anxious (→ stable)
5. **"voting results"** - 128 mentions, excited (↗️ rising)

**Insight:** Audience is highly engaged with the competition outcome. The judges' decision is controversial (mixed sentiment spike)."""
}


FEW_SHOT_EXAMPLES = [
    EXAMPLE_STATUS_CHECK,
    EXAMPLE_INVESTIGATION,
    EXAMPLE_COMPARISON,
    EXAMPLE_TRENDING
]


def get_examples_for_intent(intent: str) -> list:
    """Get relevant examples based on intent"""
    intent_map = {
        "status_check": [EXAMPLE_STATUS_CHECK, EXAMPLE_TRENDING],
        "investigation": [EXAMPLE_INVESTIGATION],
        "comparison": [EXAMPLE_COMPARISON],
        "recommendation": [EXAMPLE_STATUS_CHECK, EXAMPLE_COMPARISON]
    }
    return intent_map.get(intent, [EXAMPLE_STATUS_CHECK])
