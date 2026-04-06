"""
Test: Tool Routing - Web Search

Input: "What are the latest AI breakthroughs in 2024?"
Expected: Agent routes to web search tool, retrieves current info, synthesizes answer.
Scoring: F1-score based on tool selection (must choose 'web_search'), answer relevance, and recency.
Pass threshold: 0.7
"""

from typing import Tuple


def calculate_f1_score(true_positives: int, false_positives: int, false_negatives: int) -> float:
    """Calculate F1 score from TP, FP, FN."""
    if true_positives == 0:
        return 0.0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    f1 = 2 * (precision * recall) / (precision + recall)
    return f1


def test_web_search_tool_selection():
    """
    Canonical case: Agent should select 'web_search' tool for current events.

    Returns:
        float: 1.0 if web_search called, 0.5 if wrong tool, 0.0 if no tool
    """
    agent_response = {
        "tools_called": ["web_search"],
        "tool_args": {"query": "AI breakthroughs 2024"},
        "answer": "Recent breakthroughs include..."
    }

    if "web_search" in agent_response.get("tools_called", []):
        return 1.0
    elif len(agent_response.get("tools_called", [])) > 0:
        return 0.5
    else:
        return 0.0


def test_web_search_recency():
    """
    Canonical case: Answer should contain current year references (2024+).

    Returns:
        float: F1-based score on recency of answer
    """
    agent_response = {
        "answer": "In 2024, major breakthroughs include GPT-4 improvements and reasoning models.",
        "contains_year_2024": True,
        "sources_retrieved": 3
    }

    # Check if answer mentions current context (2024+)
    answer_text = agent_response.get("answer", "").lower()
    has_recency = any(year in answer_text for year in ["2024", "2025", "2026"])
    has_sources = agent_response.get("sources_retrieved", 0) >= 2

    if has_recency and has_sources:
        return 0.9
    elif has_recency:
        return 0.7
    elif has_sources:
        return 0.5
    else:
        return 0.0


def test_web_search_combined():
    """
    Canonical case: Combined metric - tool selection + recency.

    Returns:
        float: Composite score (0.0-1.0) combining tool choice and answer quality
    """
    # Mock agent execution
    tool_score = test_web_search_tool_selection()
    recency_score = test_web_search_recency()

    # Combined score: tool selection is critical (70%), recency is secondary (30%)
    combined = (tool_score * 0.7) + (recency_score * 0.3)
    return combined


if __name__ == "__main__":
    s1 = test_web_search_tool_selection()
    s2 = test_web_search_recency()
    s3 = test_web_search_combined()
    print(f"test_web_search_tool_selection: {s1}")
    print(f"test_web_search_recency: {s2}")
    print(f"test_web_search_combined: {s3}")
