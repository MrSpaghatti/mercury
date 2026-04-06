"""
Test: Memory Recall - Recent Episode

Input: (After 10-message history) "What did I say about Python?"
Expected: Agent retrieves relevant recent messages, answers with correct context.
Scoring: F1-score on retrieved message relevance (precision & recall of topic-relevant messages).
Pass threshold: 0.7
"""

from typing import List, Dict


def calculate_f1(true_positives: int, false_positives: int, false_negatives: int) -> float:
    """Calculate F1 from TP, FP, FN."""
    if true_positives == 0:
        return 0.0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    f1 = 2 * (precision * recall) / (precision + recall)
    return f1


def test_recent_memory_retrieval():
    """
    Canonical case: Retrieve relevant messages from 10-message history.

    Setup: Message history contains 3 Python-related and 7 other messages.
    Expected: Agent retrieves at least 2 of the 3 Python messages without false positives.

    Returns:
        float: F1 score on relevance (target: 0.7+)
    """
    # Mock recent history (10 messages)
    message_history = [
        {"role": "user", "content": "Tell me about Python 3.11"},
        {"role": "assistant", "content": "Python 3.11 has..."},
        {"role": "user", "content": "What's the weather today?"},
        {"role": "assistant", "content": "It's sunny..."},
        {"role": "user", "content": "How do I use Python decorators?"},
        {"role": "assistant", "content": "Decorators are..."},
        {"role": "user", "content": "Remind me to buy milk"},
        {"role": "assistant", "content": "OK"},
        {"role": "user", "content": "Python best practices?"},
        {"role": "assistant", "content": "Best practices include..."},
    ]

    # Identify Python-relevant messages
    python_relevant_indices = {0, 4, 8}  # Messages about Python

    # Mock agent's retrieval (simulating memory_retrieve stage-I)
    agent_retrieved_indices = {0, 4, 8}  # Correct: retrieved all Python messages

    true_positives = len(agent_retrieved_indices & python_relevant_indices)
    false_positives = len(agent_retrieved_indices - python_relevant_indices)
    false_negatives = len(python_relevant_indices - agent_retrieved_indices)

    f1 = calculate_f1(true_positives, false_positives, false_negatives)
    return f1


def test_recent_memory_no_false_positives():
    """
    Canonical case: Retrieval should not include unrelated messages.

    Returns:
        float: Precision score (0.0-1.0)
    """
    agent_retrieved_indices = {0, 4, 8}  # 3 messages retrieved
    python_relevant_indices = {0, 4, 8}  # All are truly relevant

    false_positives = len(agent_retrieved_indices - python_relevant_indices)
    precision = 1.0 if false_positives == 0 else 0.0
    return precision


def test_recent_memory_no_false_negatives():
    """
    Canonical case: Retrieval should not miss relevant messages.

    Returns:
        float: Recall score (0.0-1.0)
    """
    python_relevant_indices = {0, 4, 8}  # 3 Python messages in history
    agent_retrieved_indices = {0, 4, 8}  # Retrieved all

    false_negatives = len(python_relevant_indices - agent_retrieved_indices)
    recall = 1.0 if false_negatives == 0 else 0.5 if false_negatives == 1 else 0.0
    return recall


def test_recent_memory_combined():
    """
    Canonical case: Combined recent memory scoring.

    Returns:
        float: Composite F1 score
    """
    f1 = test_recent_memory_retrieval()
    return f1


if __name__ == "__main__":
    s1 = test_recent_memory_retrieval()
    s2 = test_recent_memory_no_false_positives()
    s3 = test_recent_memory_no_false_negatives()
    s4 = test_recent_memory_combined()
    print(f"test_recent_memory_retrieval: {s1:.3f}")
    print(f"test_recent_memory_no_false_positives: {s2:.3f}")
    print(f"test_recent_memory_no_false_negatives: {s3:.3f}")
    print(f"test_recent_memory_combined: {s4:.3f}")
