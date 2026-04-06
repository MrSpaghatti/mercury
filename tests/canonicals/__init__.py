"""
Canonical eval test cases for Mercury agent.

These tests define the baseline reference behavior for the agent.
Each test returns a score 0.0-1.0 where 1.0 = perfect behavior.

Test cases cover all decision branches:
- Simple factual (no tool)
- Tool routing (web search, file ops)
- Memory recall (recent & semantic)
- Memory miss (novel topic)
- Multi-step execution
- Ambiguous intent
- Injection prevention
- Context pruning under load
"""
