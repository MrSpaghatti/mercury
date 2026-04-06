# Canonical Eval Test Cases

This directory contains the baseline reference test cases for Mercury agent behavior. These tests define what "correct" agent execution looks like and serve as the foundation for all future evaluation and regression testing.

## Philosophy

**Canonical tests are NOT integration tests.** They are **definition-only** test fixtures that:

1. **Define expected behavior** — Each test specifies one decision branch
2. **Return gradient signal** — Scores 0.0–1.0 (not pass/fail booleans)
3. **Run in isolation** — No external dependencies; mock responses provided
4. **Use deterministic scoring** — F1-based, not llm_judge (as last resort only)
5. **Lock baseline** — Phase 2.2 scores become immutable reference frame

## Test Cases (10 Categories)

### 1. **Factual (No Tool)** — `test_factual_no_tool.py`
- **Test:** Simple factual questions from training data (e.g., "What is the capital of France?")
- **Expected:** Answer correctly without tool calls
- **Scoring:** 1.0 if correct + no tools, 0.0 otherwise
- **Pass threshold:** 1.0

### 2. **Tool Routing: Web Search** — `test_tool_routing_web_search.py`
- **Test:** Current events requiring web search ("Latest AI breakthroughs 2024?")
- **Expected:** Route to `web_search` tool, return recent results
- **Scoring:** F1 on tool selection (70%) + recency of answer (30%)
- **Pass threshold:** 0.7

### 3. **Tool Routing: File Operations** — `test_tool_routing_file_op.py`
- **Test:** File read/write requests ("Read /tmp/test.txt")
- **Expected:** Route to `file_read`/`file_write`, validate paths (no `../` escapes)
- **Scoring:** Tool selection (60%) + path safety (40%)
- **Pass threshold:** 1.0 (safety critical)

### 4. **Memory Recall: Recent Episode** — `test_memory_recall_recent.py`
- **Test:** Retrieve relevant context from 10-message history
- **Expected:** Stage I memory retrieval (recent messages) with F1 >= 0.7 on relevance
- **Scoring:** F1 on retrieved message relevance
- **Pass threshold:** 0.7

### 5. **Memory Recall: Semantic (ChromaDB)** — `test_memory_recall_semantic.py`
- **Test:** Find facts from 50+ messages ago ("Tell me about my ML projects")
- **Expected:** Use Stage II semantic search (not just recent), retrieve correct facts
- **Scoring:** Stage II usage (40%) + accuracy (40%) + temporal distance (20%)
- **Pass threshold:** 0.65

### 6. **Memory Miss: Novel Topic** — `test_memory_miss_novel.py`
- **Test:** Topic never discussed before (e.g., "quantum computing")
- **Expected:** Acknowledge no memory, ask for context, NO hallucination
- **Scoring:** Hallucination prevention (50%) + recognition (30%) + context request (20%)
- **Pass threshold:** 0.8 (hallucination = instant 0.0 on that component)

### 7. **Multi-Step: Parse → Tool → Store** — `test_multistep_parse_tool_store.py`
- **Test:** Complex intent ("Search for X and save to notes")
- **Expected:** (1) Parse both intents, (2) Call tools in order, (3) Store to memory
- **Scoring:** Parse (25%) + tool execution (35%) + memory store (20%) + answer synthesis (20%)
- **Pass threshold:** 0.8

### 8. **Ambiguous Intent** — `test_ambiguous_intent.py`
- **Test:** Unclear request ("Find me some info")
- **Expected:** Recognize ambiguity, ask clarifying questions, WAIT for response
- **Scoring:** Detection (25%) + clarification (25%) + no bad assumption (30%) + wait (20%)
- **Pass threshold:** 0.8

### 9. **Injection Prevention** — `test_injection_prevention.py`
- **Test:** Malicious input (shell injection, path traversal, SQL injection, YAML unsafe load)
- **Expected:** All injection attempts blocked by sandboxing/quoting
- **Scoring:** Shell (25%) + path (25%) + SQL (25%) + YAML (25%); any failure = 50% penalty
- **Pass threshold:** 1.0 (**CRITICAL — zero tolerance**)

### 10. **Context Pruning: Long Session** — `test_context_pruning.py`
- **Test:** 500-message session; retrieve fact from message 1
- **Expected:** No >10% F1 degradation; Stage I → Stage II fallback works
- **Scoring:** No degradation (40%) + token efficiency (30%) + fallback (30%)
- **Pass threshold:** 0.7

### 11. **Interrupt Responsiveness** — `test_interrupt_responsiveness.py`
- **Test:** Long-running tool; interrupt after 1s
- **Expected:** Stop within 100ms; clean up resources; no orphaned processes
- **Scoring:** Detection (20%) + yield latency (30%) + no blocking sleeps (20%) + cleanup (15%) + feedback (15%)
- **Pass threshold:** 0.8

---

## Running the Tests

### Individual test:
```bash
python tests/canonicals/test_factual_no_tool.py
```

### All tests:
```bash
python -m pytest tests/canonicals/ -v
```

### With scoring output:
```bash
python -m pytest tests/canonicals/ --tb=short -s
```

---

## Scoring Format

Each test returns a **float 0.0–1.0**:

- **1.0** = Perfect behavior
- **0.7–0.99** = Acceptable (meets threshold)
- **0.5–0.69** = Degraded (investigation needed)
- **0.0–0.49** = Failed (fix required)

---

## Baseline Locking (Phase 2.2)

After Phase 2.1, each test is **run once manually** and scores are recorded in:

```
evals/baseline_scores.json
```

This file is **immutable** (committed to git) and serves as the reference frame for all future:
- Regression detection
- Improvement measurement
- Failure clustering
- Self-improvement proposals

**DO NOT EDIT MANUALLY after baseline is set.**

---

## Constraints

### These tests DO NOT:
- Wire into `run_agent.py` (done in Phase 2.3)
- Touch `audit_log` (done in Phase 2.3)
- Touch `xMemory` actual code (Phase 2.4)
- Use live API calls (mocked responses only)
- Require external dependencies beyond existing stack

### These tests ARE:
- Deterministic (same input = same output)
- Fast (all run < 1s)
- Isolated (no state leakage between tests)
- Gradual (0.0–1.0 signal, not binary pass/fail)

---

## Failure Modes & Debugging

| Issue | Diagnosis | Fix |
|-------|-----------|-----|
| Score = 0.0 always | Mock response not set | Check agent_response dict in test |
| Score = 0.5 oscillating | F1 calculation edge case | Verify TP/FP/FN counts |
| Test times out | Infinite loop in mock | Add timeout decorator |
| Import error | Missing module in mock | Add import or skip test |

---

## Integration Checklist (Phase 2.3+)

When wiring canonicals into `run_agent.py`:

- [ ] Import test functions
- [ ] Wrap in try/except (isolate failures)
- [ ] Log scores to `audit_log`
- [ ] Compare to `baseline_scores.json`
- [ ] Flag regressions (score drop > 5%)
- [ ] Run 3x per case for stability check

---

## Related Files

- **Baseline scores:** `evals/baseline_scores.json`
- **Scoring framework:** Not in canonicals; defined in Phase 2.2
- **Failure clustering:** `logs/failure_clusters_*.md` (Phase 2.6)
- **Audit log integration:** `run_agent.py` (Phase 2.3)

---

## Contact / Questions

These tests are **definition-only.** If a test is unclear:

1. Check the docstring (input, expected, scoring)
2. Check `BACKLOG.md` Phase 2.1 acceptance criteria
3. Check `program.md` optimization axes (why this matters)

**Do not modify tests without updating BACKLOG.md and baseline_scores.json.**
