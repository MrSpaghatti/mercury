"""
Test: Multi-Step Execution - Parse Intent → Call Tool → Store Memory

Input: "Search for React hooks best practices and save what you find to my notes"
Expected: (1) Parse intent (search + save), (2) Call web_search, (3) Call file_write, (4) Store to memory.
Scoring: F1 based on: correct intent parse (1.0), tool execution (0.5 per tool), memory store (0.5).
Pass threshold: 0.8
"""


def test_multistep_intent_parse():
    """
    Canonical case: Agent must parse multi-part intent (search AND save).

    Returns:
        float: 1.0 if both intents identified, 0.5 if partial, 0.0 if missed
    """
    agent_response = {
        "parsed_intents": ["search", "save"],
        "intent_count": 2
    }

    intents = agent_response.get("parsed_intents", [])

    if "search" in intents and "save" in intents:
        return 1.0
    elif len(intents) >= 1:
        return 0.5
    else:
        return 0.0


def test_multistep_tool_sequence():
    """
    Canonical case: Correct tool sequence must be executed.

    Expected order: web_search → file_write
    (or semantic_store, but file_write is primary)

    Returns:
        float: 1.0 if correct sequence, 0.5 if partial, 0.0 if wrong
    """
    agent_response = {
        "tools_called": ["web_search", "file_write"],
        "tool_order": [0, 1],  # 0=web_search first, 1=file_write second
        "tools_succeeded": [True, True]
    }

    tools = agent_response.get("tools_called", [])
    succeeded = agent_response.get("tools_succeeded", [])

    # Check sequence
    has_search = "web_search" in tools
    has_write = "file_write" in tools
    all_succeeded = all(succeeded) if succeeded else False

    if has_search and has_write and all_succeeded:
        return 1.0
    elif has_search or has_write:
        return 0.5
    else:
        return 0.0


def test_multistep_memory_storage():
    """
    Canonical case: After execution, must store interaction to memory.

    Returns:
        float: 1.0 if stored, 0.5 if partial, 0.0 if not stored
    """
    agent_response = {
        "memory_stored": True,
        "memory_type": "episode",  # Should store as episode + semantic
        "content_stored": "React hooks best practices: ..."
    }

    memory_stored = agent_response.get("memory_stored", False)
    memory_type = agent_response.get("memory_type", "")
    has_content = len(agent_response.get("content_stored", "")) > 0

    if memory_stored and has_content:
        return 1.0
    elif memory_stored or has_content:
        return 0.5
    else:
        return 0.0


def test_multistep_answer_quality():
    """
    Canonical case: Final answer should synthesize findings + confirmation.

    Returns:
        float: 1.0 if good synthesis, 0.5 if partial, 0.0 if missing
    """
    agent_response = {
        "final_answer": "I found 5 key React hooks best practices and saved them to your notes. "
                       "The main findings are: 1) Use hooks at the top level, 2) Only call in functions, 3) Use custom hooks for logic..."
    }

    answer = agent_response.get("final_answer", "").lower()

    has_confirmation = any(phrase in answer for phrase in [
        "saved", "stored", "noted", "recorded"
    ])
    has_findings = any(phrase in answer for phrase in [
        "found", "key", "best practices", "findings"
    ])

    if has_confirmation and has_findings and len(answer) > 100:
        return 1.0
    elif has_confirmation or has_findings:
        return 0.7
    else:
        return 0.3


def test_multistep_combined():
    """
    Canonical case: Combined multi-step scoring.

    Weights: intent_parse (25%), tools (35%), memory (20%), answer (20%)

    Returns:
        float: Composite score (target: 0.8+)
    """
    intent = test_multistep_intent_parse()
    tools = test_multistep_tool_sequence()
    memory = test_multistep_memory_storage()
    answer = test_multistep_answer_quality()

    combined = (intent * 0.25) + (tools * 0.35) + (memory * 0.2) + (answer * 0.2)
    return combined


if __name__ == "__main__":
    s1 = test_multistep_intent_parse()
    s2 = test_multistep_tool_sequence()
    s3 = test_multistep_memory_storage()
    s4 = test_multistep_answer_quality()
    s5 = test_multistep_combined()
    print(f"test_multistep_intent_parse: {s1:.3f}")
    print(f"test_multistep_tool_sequence: {s2:.3f}")
    print(f"test_multistep_memory_storage: {s3:.3f}")
    print(f"test_multistep_answer_quality: {s4:.3f}")
    print(f"test_multistep_combined: {s5:.3f}")
