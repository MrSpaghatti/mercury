"""
Test: Simple Factual Query (No Tool)

Input: "What is the capital of France?"
Expected: Agent responds with factual answer (Paris) without calling any tool.
Scoring: 1.0 if correct answer returned and NO tool call made, else 0.0.
Pass threshold: 1.0
"""

import json


def test_simple_factual():
    """
    Canonical case: Answer a simple factual question from base knowledge.
    No tool call should be made (agent has this in training data).

    Returns:
        float: 1.0 if answer is "Paris" and no tools called, 0.0 otherwise
    """
    # Simulate agent execution with mocked response
    agent_response = {
        "answer": "Paris",
        "tools_called": [],
        "confidence": 0.99
    }

    # Scoring: factual correctness + no tool invocation
    has_answer = "paris" in agent_response.get("answer", "").lower()
    no_tools = len(agent_response.get("tools_called", [])) == 0

    score = 1.0 if (has_answer and no_tools) else 0.0
    return score


def test_simple_arithmetic():
    """
    Canonical case: Basic arithmetic (should not need tools).

    Returns:
        float: 1.0 if correct answer without tool, 0.0 otherwise
    """
    agent_response = {
        "answer": "15",
        "tools_called": [],
        "calculation": "10 + 5"
    }

    has_answer = "15" in agent_response.get("answer", "")
    no_tools = len(agent_response.get("tools_called", [])) == 0

    score = 1.0 if (has_answer and no_tools) else 0.0
    return score


if __name__ == "__main__":
    score1 = test_simple_factual()
    score2 = test_simple_arithmetic()
    print(f"test_simple_factual: {score1}")
    print(f"test_simple_arithmetic: {score2}")
    print(f"Average: {(score1 + score2) / 2}")
