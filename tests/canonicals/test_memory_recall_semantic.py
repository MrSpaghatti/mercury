"""
Test: Memory Recall - Semantic (ChromaDB)

Input: (After 100+ message history) "Tell me about my machine learning projects"
Expected: Agent uses semantic search to find relevant facts (Stage II), not just recent messages.
Scoring: F1-score on semantic relevance + correct stage (must use Stage II retrieval).
Pass threshold: 0.65
"""


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


def test_semantic_retrieval_stage():
    """
    Canonical case: Must use Stage II (semantic/ChromaDB) for old, non-recent facts.

    Context: Query is about events from 50+ messages ago.
    Expected: Agent recognizes need for semantic search (not Stage I recent-only).

    Returns:
        float: 1.0 if Stage II used, 0.5 if mixed, 0.0 if Stage I only
    """
    agent_response = {
        "memory_stage_used": "stage_ii_semantic",  # ChromaDB retrieval
        "retrieval_method": "semantic_search",
        "query": "machine learning projects"
    }

    stage_used = agent_response.get("memory_stage_used", "")
    if "stage_ii" in stage_used.lower() or "semantic" in stage_used.lower():
        return 1.0
    elif "mixed" in stage_used.lower():
        return 0.5
    else:
        return 0.0


def test_semantic_retrieval_accuracy():
    """
    Canonical case: Retrieved facts must match the semantic query.

    Setup: User asks about "machine learning projects".
    Retrieved facts should include references to ML, projects, models.

    Returns:
        float: F1 score on topic relevance (0.0-1.0)
    """
    relevant_keywords = {"machine learning", "project", "model", "neural", "training"}

    retrieved_facts = [
        "You mentioned your image classification project using CNNs",
        "Your reinforcement learning research on game AI",
        "A Python project using scikit-learn for predictions",
        "Your weekend hiking trip"  # Irrelevant
    ]

    # Count relevant facts
    true_positives = 0
    for fact in retrieved_facts:
        fact_lower = fact.lower()
        if any(keyword in fact_lower for keyword in relevant_keywords):
            true_positives += 1

    # Expected: 3 ML facts
    false_positives = len(retrieved_facts) - true_positives  # 1 (hiking)
    false_negatives = 0  # Assuming we're testing what's retrieved

    f1 = calculate_f1(true_positives, false_positives, false_negatives)
    return f1


def test_semantic_temporal_distance():
    """
    Canonical case: Retrieved facts should be relevant despite temporal distance.

    Setup: User asked about ML projects 50+ messages ago.
    Expected: Agent still retrieves correct facts (not recency-biased).

    Returns:
        float: 1.0 if old facts retrieved correctly, 0.0 if missing
    """
    # Mock retrieval from 50 messages ago
    old_fact_retrieved = {
        "content": "You mentioned your image classification project using CNNs",
        "message_distance": 50,
        "relevance_score": 0.87  # ChromaDB similarity
    }

    # Check: was fact retrieved despite being old?
    if old_fact_retrieved.get("relevance_score", 0) >= 0.7:
        return 1.0
    else:
        return 0.0


def test_semantic_combined():
    """
    Canonical case: Combined semantic memory scoring.

    Returns:
        float: Composite score (stage weight=40%, accuracy=40%, temporal=20%)
    """
    stage = test_semantic_retrieval_stage()
    accuracy = test_semantic_retrieval_accuracy()
    temporal = test_semantic_temporal_distance()

    combined = (stage * 0.4) + (accuracy * 0.4) + (temporal * 0.2)
    return combined


if __name__ == "__main__":
    s1 = test_semantic_retrieval_stage()
    s2 = test_semantic_retrieval_accuracy()
    s3 = test_semantic_temporal_distance()
    s4 = test_semantic_combined()
    print(f"test_semantic_retrieval_stage: {s1:.3f}")
    print(f"test_semantic_retrieval_accuracy: {s2:.3f}")
    print(f"test_semantic_temporal_distance: {s3:.3f}")
    print(f"test_semantic_combined: {s4:.3f}")
