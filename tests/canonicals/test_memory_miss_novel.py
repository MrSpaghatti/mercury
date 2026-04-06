"""
Test: Memory Miss - Novel Topic

Input: "Tell me about my experience with quantum computing" (never mentioned before)
Expected: Agent recognizes no relevant history, states clearly ("I don't have..."), doesn't hallucinate.
Scoring: 1.0 if agent says "no memory" or asks for info, 0.0 if hallucination.
Pass threshold: 1.0
"""


def test_memory_miss_recognition():
    """
    Canonical case: Agent should recognize when memory is empty for a topic.

    Setup: Query is about a topic never discussed (e.g., quantum computing).
    Expected: Agent should NOT claim to have information about this.

    Returns:
        float: 1.0 if agent acknowledges no memory, 0.0 if hallucinate
    """
    agent_response = {
        "answer": "I don't have any memory of discussions about quantum computing.",
        "memory_found": False,
        "confidence": 1.0
    }

    answer_text = agent_response.get("answer", "").lower()
    memory_found = agent_response.get("memory_found", False)

    # Check for hallucination indicators
    has_hallucination = any(phrase in answer_text for phrase in [
        "you mentioned quantum",
        "you discussed quantum",
        "you worked on quantum",
        "i remember you talking about quantum"
    ])

    # Check for proper "no memory" acknowledgment
    has_no_memory_statement = any(phrase in answer_text for phrase in [
        "i don't have",
        "no memory",
        "not found",
        "never mentioned",
        "no record"
    ])

    if has_hallucination:
        return 0.0
    elif has_no_memory_statement and not memory_found:
        return 1.0
    else:
        return 0.5


def test_memory_miss_ask_for_context():
    """
    Canonical case: Agent should ask for context instead of inventing.

    Returns:
        float: 1.0 if asks for info, 0.5 if vague, 0.0 if hallucinate
    """
    agent_response = {
        "answer": "I don't have prior knowledge of your quantum computing experience. Could you tell me about it?",
        "asks_for_context": True
    }

    answer_text = agent_response.get("answer", "").lower()
    asks_for_info = agent_response.get("asks_for_context", False)

    # Check for asking for more information
    has_question = "?" in agent_response.get("answer", "")
    asks_user = any(phrase in answer_text for phrase in [
        "could you tell",
        "can you share",
        "what is your",
        "tell me about",
        "please share"
    ])

    if asks_user and has_question:
        return 1.0
    elif asks_for_info:
        return 0.8
    else:
        return 0.5


def test_memory_miss_no_hallucination():
    """
    Canonical case: Strict check - no invented facts.

    Returns:
        float: 1.0 if clean (no invention), 0.0 if any hallucination
    """
    agent_response = {
        "answer": "I don't have any previous discussions about quantum computing."
    }

    hallucination_indicators = [
        "you said",
        "you mentioned",
        "you discussed",
        "you told me",
        "i remember you",
        "previously you",
        "last time you"
    ]

    answer_text = agent_response.get("answer", "").lower()

    # Strict check: no hallucination allowed
    has_hallucination = any(indicator in answer_text for indicator in hallucination_indicators)

    return 0.0 if has_hallucination else 1.0


def test_memory_miss_combined():
    """
    Canonical case: Combined memory miss scoring.

    Returns:
        float: Composite score
    """
    recognition = test_memory_miss_recognition()
    context_ask = test_memory_miss_ask_for_context()
    no_hallucination = test_memory_miss_no_hallucination()

    # Hallucination prevention is most critical (50%)
    combined = (no_hallucination * 0.5) + (recognition * 0.3) + (context_ask * 0.2)
    return combined


if __name__ == "__main__":
    s1 = test_memory_miss_recognition()
    s2 = test_memory_miss_ask_for_context()
    s3 = test_memory_miss_no_hallucination()
    s4 = test_memory_miss_combined()
    print(f"test_memory_miss_recognition: {s1:.3f}")
    print(f"test_memory_miss_ask_for_context: {s2:.3f}")
    print(f"test_memory_miss_no_hallucination: {s3:.3f}")
    print(f"test_memory_miss_combined: {s4:.3f}")
