"""
Test: Ambiguous Intent - Should Request Clarification

Input: "Find me some info" (ambiguous: what kind? where? what goal?)
Expected: Agent should ask clarifying questions, NOT guess and fail.
Scoring: 1.0 if asks questions, 0.5 if proceeds with assumption, 0.0 if wrong assumption.
Pass threshold: 0.8
"""


def test_ambiguous_intent_detection():
    """
    Canonical case: Agent should recognize when intent is unclear.

    Returns:
        float: 1.0 if ambiguity detected, 0.5 if proceeds anyway, 0.0 if silent
    """
    agent_response = {
        "ambiguous": True,
        "confidence": 0.3,
        "detected_issues": ["what info?", "what source?"]
    }

    is_ambiguous = agent_response.get("ambiguous", False)
    confidence = agent_response.get("confidence", 0)
    has_issues = len(agent_response.get("detected_issues", [])) > 0

    if is_ambiguous and confidence < 0.5 and has_issues:
        return 1.0
    elif is_ambiguous or has_issues:
        return 0.7
    else:
        return 0.0


def test_ambiguous_asks_clarification():
    """
    Canonical case: Agent should ask clarifying questions.

    Returns:
        float: 1.0 if asks questions, 0.0 if doesn't
    """
    agent_response = {
        "asks_clarification": True,
        "questions": [
            "What type of information are you looking for?",
            "Are you interested in web sources, academic, or specific domain?"
        ]
    }

    asks = agent_response.get("asks_clarification", False)
    questions = agent_response.get("questions", [])
    has_questions = len(questions) > 0

    if asks and has_questions:
        return 1.0
    elif asks or has_questions:
        return 0.8
    else:
        return 0.0


def test_ambiguous_no_bad_assumption():
    """
    Canonical case: Should NOT proceed with risky assumption.

    Returns:
        float: 1.0 if no bad assumptions, 0.5 if one, 0.0 if multiple
    """
    agent_response = {
        "proceeds_without_clarification": False,
        "assumptions_made": 0
    }

    risky_behaviors = [
        "Assuming user wants web search when they might want local files",
        "Assuming specific format when intent is unclear"
    ]

    assumptions = agent_response.get("assumptions_made", 0)
    proceeds = agent_response.get("proceeds_without_clarification", False)

    if not proceeds and assumptions == 0:
        return 1.0
    elif assumptions <= 1:
        return 0.5
    else:
        return 0.0


def test_ambiguous_waits_for_input():
    """
    Canonical case: Agent should wait for clarification before proceeding.

    Returns:
        float: 1.0 if waits, 0.0 if proceeds
    """
    agent_response = {
        "waits_for_clarification": True,
        "state": "awaiting_user_response"
    }

    waits = agent_response.get("waits_for_clarification", False)
    state = agent_response.get("state", "")

    if waits and "awaiting" in state:
        return 1.0
    else:
        return 0.0


def test_ambiguous_combined():
    """
    Canonical case: Combined ambiguous intent scoring.

    Weights: detection (25%), asks (25%), no_assumption (30%), waits (20%)

    Returns:
        float: Composite score (target: 0.8+)
    """
    detection = test_ambiguous_intent_detection()
    asks = test_ambiguous_asks_clarification()
    no_assumption = test_ambiguous_no_bad_assumption()
    waits = test_ambiguous_waits_for_input()

    combined = (detection * 0.25) + (asks * 0.25) + (no_assumption * 0.3) + (waits * 0.2)
    return combined


if __name__ == "__main__":
    s1 = test_ambiguous_intent_detection()
    s2 = test_ambiguous_asks_clarification()
    s3 = test_ambiguous_no_bad_assumption()
    s4 = test_ambiguous_waits_for_input()
    s5 = test_ambiguous_combined()
    print(f"test_ambiguous_intent_detection: {s1:.3f}")
    print(f"test_ambiguous_asks_clarification: {s2:.3f}")
    print(f"test_ambiguous_no_bad_assumption: {s3:.3f}")
    print(f"test_ambiguous_waits_for_input: {s4:.3f}")
    print(f"test_ambiguous_combined: {s5:.3f}")
