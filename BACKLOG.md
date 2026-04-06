# Mercury North Star — Phase 2 Backlog

**Last Updated:** April 6, 2026  
**Phase 1 Status:** ✅ Complete (95%, sandboxing in progress)  
**Current Focus:** Phase 2 Canonical Eval Harness

---

## Critical Sequencing (MUST FOLLOW THIS ORDER)

```
Baseline Canonicals (2.1)
         ↓
    Baseline Scores (2.2)  ← Reference frame locked in
         ↓
   Audit Integration (2.3)  ← Only NOW can you start collecting data
         ↓
  xMemory Wiring (2.4)      ← Scaffold becomes live
         ↓
Regression Testing (2.5)    ← Verify no breakage
         ↓
Failure Clustering (2.6)    ← Only NOW has real signal
         ↓
Sandboxing (2.7)           ← Completes security boundary
```

**DO NOT SKIP STEPS.** If you wire 2.3 before 2.1–2.2, you have signal but no baseline to compare against.

---

## Backlog Items (In Priority Order)

### Phase 2.1: Define Canonical Eval Cases
**Blocking:** All subsequent work  
**Effort:** 2–4 hours  
**Owner:** Next session  

**What:** Create 5–10 test cases that define what "correct" agent behavior looks like.

**Acceptance Criteria:**
- [ ] 5+ canonical test cases in `tests/canonicals/test_*.py`
- [ ] Each case: clear intent → expected tool choice → expected output
- [ ] Coverage: tool_routing, memory_retrieve, intent_parse, injection_prevention, timeout_handling
- [ ] Each case runnable in isolation
- [ ] Each case returns 0.0–1.0 score (pass/fail)

**Examples:**
```python
# tests/canonicals/test_tool_routing_search.py
def test_retrieve_from_history():
    """Retrieve relevant context from 10-message history"""
    # Setup: 10 messages, user asks "what did I say about X"
    # Expected: memory_retrieve called, F1≥0.7 on relevance
    # Measurement: retrieved_messages_f1 ≥ 0.7

# tests/canonicals/test_injection_prevention.py
def test_command_injection_blocked():
    """Command injection attempt is blocked"""
    # Setup: user input with shell metacharacters
    # Expected: subprocess call quoted, injection not executed
    # Measurement: pass if system doesn't execute injected command
```

**Definition of Done:**
- Canonical test suite runs cleanly
- Each case has a measurable score (0.0–1.0)
- Cases cover diverse decision types (not just happy path)

---

### Phase 2.2: Manual Baseline Scoring
**Blocking:** All subsequent work  
**Depends on:** 2.1 (canonicals exist)  
**Effort:** 1–2 hours  
**Owner:** Next session  

**What:** Run each canonical case once manually, record scores. This becomes the reference frame for all future work.

**Acceptance Criteria:**
- [ ] All 5–10 cases run successfully
- [ ] `evals/baseline_scores.json` created with format:
  ```json
  {
    "test_tool_routing_search": 0.85,
    "test_injection_prevention": 1.0,
    "test_memory_retrieve_empty_history": 0.0,
    ...
  }
  ```
- [ ] Average baseline ≥ 0.7 (if not, fix canonicals before proceeding)
- [ ] Baseline file committed to git (immutable reference)

**Why This Matters:**
- Every change after this point is measured against baseline_scores.json
- If you skip this, you have no reference frame for "improvement" vs "regression"

---

### Phase 2.3: Integrate audit_log into run_agent.py
**Blocking:** 2.6 (failure clustering needs data)  
**Depends on:** 2.1–2.2 (have reference frame)  
**Effort:** 2–3 hours  
**Owner:** Next session  

**What:** Wire audit_log calls into key decision points in run_agent.py.

**Instrumentation Points:**
```python
# Before tool execution (line ~6100)
audit.log_tool_execution(
    session_id=effective_task_id,
    tool_name=tool_call.function.name,
    context={
        "input_intent": assistant_message.content[:100],
        "tool_args": tool_call.function.arguments,
    }
)

# After tool execution
audit.log_tool_execution(
    session_id=effective_task_id,
    tool_name=tool_call.function.name,
    failure_reason=None if success else "timeout" | "error",
    context={
        "response_time_ms": elapsed_ms,
        "error": str(exception) if failed else None
    }
)

# In memory retrieval (if exists in codebase)
audit.log_memory_retrieve(
    session_id=effective_task_id,
    memory_hit=len(retrieved_context) > 0,
    context={
        "query": query_string,
        "retrieved_count": len(retrieved_context)
    }
)
```

**Acceptance Criteria:**
- [ ] AuditLog instance initialized on agent startup
- [ ] Tool execution logged before + after
- [ ] Memory retrieval logged (if applicable)
- [ ] Intent parse logged (if applicable)
- [ ] Audit entries visible in `hermes_state.db` audit_log table
- [ ] No audit I/O errors (failures are logged, not raised)

**Verification:**
```bash
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM audit_log;" # should grow
```

---

### Phase 2.4: Wire xMemory into Session Flow
**Blocking:** 2.6 (failure clustering)  
**Depends on:** 2.1–2.3 (canonicals defined, audit integrated)  
**Effort:** 2–3 hours  
**Owner:** Next session  

**What:** Integrate XMemoryStack into session initialization and prompt building.

**Integration Points:**
```python
# In __init__ or session startup (run_agent.py, line ~200)
from agent.xmemory import XMemoryStack
self.xmemory = XMemoryStack(
    db_path=str(get_hermes_home() / "episodes.db"),
    chroma_path=str(get_hermes_home() / "chroma_db")
)

# After each agent turn (before next message loop)
self.xmemory.store_interaction(
    user_id=user_id_or_session_hash,
    user_message=messages[-2]["content"],  # user's last message
    agent_response=response_text           # agent's response
)

# In prompt building (system_prompt construction)
context = self.xmemory.build_context(user_id, current_message)
system_prompt = f"""
... existing system prompt ...

## Relevant Context
Recent episodes: {json.dumps(context['recent_episodes'], indent=2)}
Related facts: {json.dumps(context['relevant_facts'][:3], indent=2)}
User themes: {json.dumps(context['themes'], indent=2)}
"""
```

**Acceptance Criteria:**
- [ ] XMemoryStack initializes without errors
- [ ] store_interaction() called after each agent turn
- [ ] build_context() returns valid structure
- [ ] Context included in system prompt (visible to model)
- [ ] ChromaDB collection growing (new facts stored)
- [ ] SQLite episode table growing (new episodes logged)

**Verification:**
```bash
# Episodes should grow
sqlite3 episodes.sqlite "SELECT COUNT(*) FROM episodes;"

# Chroma should have collection
python -c "import chromadb; c = chromadb.PersistentClient('./chroma_db'); print(c.get_or_create_collection('semantics').count())"
```

---

### Phase 2.5: Regression Test Canonicals
**Blocking:** 2.6 (safe to proceed)  
**Depends on:** 2.4 (xMemory + audit wired)  
**Effort:** 1 hour  
**Owner:** Next session  

**What:** Run canonicals again against the wired system. Verify no regression vs baseline_scores.json.

**Acceptance Criteria:**
- [ ] All canonicals run successfully
- [ ] New scores recorded in `evals/session_YYYYMMDD_scores.json`
- [ ] Each case run 3× (stability check)
- [ ] No case regressed by >5% from baseline
- [ ] If regression found: debug, fix, re-run until passing

**Example Session Scores:**
```json
{
  "session": "2026-04-13",
  "run1": {
    "test_tool_routing_search": 0.82,
    "test_injection_prevention": 1.0,
    ...
  },
  "run2": {
    "test_tool_routing_search": 0.84,
    ...
  },
  "run3": {
    "test_tool_routing_search": 0.83,
    ...
  },
  "average": {
    "test_tool_routing_search": 0.83,
    "deviation_from_baseline": -0.02
  }
}
```

**Pass Criteria:**
- All cases: `deviation_from_baseline ≥ -0.05` (5% tolerance)
- If any fails: investigate, fix, re-test

---

### Phase 2.6: Implement Failure Clustering
**Blocking:** 2.7, Phase 3 (autoagent loop)  
**Depends on:** 2.3–2.5 (audit_log has real data)  
**Effort:** 2–3 hours  
**Owner:** Session after 2.5  

**What:** Weekly batch analysis of audit_log to identify failure patterns.

**Implementation:**
```python
# scripts/failure_clustering.py (new file)
import sqlite3
from pathlib import Path
from collections import defaultdict

db_path = Path.home() / ".hermes" / "state.db"
with sqlite3.connect(db_path) as conn:
    cursor = conn.execute("""
        SELECT intent_category, failure_reason, COUNT(*) as count, COUNT(DISTINCT session_id) as sessions
        FROM audit_log
        WHERE failure_reason IS NOT NULL
          AND timestamp > datetime('now', '-7 days')
        GROUP BY intent_category, failure_reason
        ORDER BY count DESC
        LIMIT 10
    """)
    patterns = cursor.fetchall()

# Output: logs/failure_clusters_YYYY-MM-DD.md
report = f"# Failure Clusters (Last 7 days)\n\n"
for intent, reason, count, sessions in patterns:
    report += f"- **{intent} / {reason}**: {count} occurrences across {sessions} sessions\n"

Path("logs/failure_clusters_YYYY-MM-DD.md").write_text(report)
```

**Acceptance Criteria:**
- [ ] Failure clustering script written and runnable
- [ ] Groups audit_log by (intent_category, failure_reason)
- [ ] Top 5 patterns identified weekly
- [ ] Output to `logs/failure_clusters_*.md`
- [ ] New patterns trigger new eval cases (loop back to 2.1)

**Definition of Done:**
- Script runs without errors
- Report identifies top 3–5 patterns
- Each pattern mapped to a new eval case (if novel)

---

### Phase 2.7: Finish Subprocess Sandboxing
**Blocking:** Phase 3 (autoagent loop)  
**Depends on:** Nothing (can be parallelized)  
**Status:** 🔄 In progress (Jules ID: 1952571512354332496)  
**Effort:** (Already in flight, maybe 1–2 more hours)  
**Owner:** Next session (or when Jules completes)  

**What:** Complete bwrap/seccomp wrapper and wire into tool execution.

**Acceptance Criteria:**
- [ ] Jules session 1952571512354332496 completes
- [ ] `tools/sandbox.py` implements SandboxedExecutor class
- [ ] All subprocess calls wrapped with bwrap isolation
- [ ] Tests verify:
  - Subprocess can write to /tmp
  - Subprocess cannot access /home, /root
  - Network calls blocked
  - Overhead <50ms per call

**Verification:**
```bash
# Run a malicious command that tries to escape sandbox
python -c "
from tools.sandbox import SandboxedExecutor
executor = SandboxedExecutor()
result = executor.run(['bash', '-c', 'cat /etc/passwd'])
# Should fail or return permission denied
"
```

---

## Dependency Graph

```
2.1 (Canonicals)
  ↓
2.2 (Baseline)
  ├→ 2.3 (Audit wiring)
  │   ├→ 2.5 (Regression test)
  │   │   └→ 2.6 (Failure clustering)
  │   │       └→ Phase 3 (Autoagent loop)
  │   └→ 2.4 (xMemory wiring)
  │       └→ 2.5 (Regression test)
  │
  └→ 2.7 (Sandboxing) [can parallelize with 2.3–2.4]
      └→ Phase 3 (Autoagent loop)
```

**Critical Path:** 2.1 → 2.2 → 2.3 → 2.5 → 2.6 (total ~15 hours)  
**Can Parallelize:** 2.7 (sandboxing) during 2.3–2.4

---

## Success Metrics

After 2.1–2.6 complete:
- [ ] 5–10 canonicals defined + baseline scores locked
- [ ] Audit_log capturing 100+ entries per day (real usage)
- [ ] xMemory storing and retrieving episodes/facts
- [ ] Canonicals still passing (regression tests clean)
- [ ] Top 5 failure patterns identified and categorized
- [ ] Sandboxing live (zero filesystem escapes)

This unlocks Phase 3: autoagent loop can now accept/reject changes based on eval scores.

---

## Notes for Next Session

- **Start here:** 2.1 (Canonicals). This is the critical blocker.
- **Read these first:** HANDOFF.md, program.md, ROADMAP.md, this file
- **Don't skip 2.2:** Baseline scores are the reference frame for everything after
- **Parallel work:** 2.7 (sandboxing) can happen alongside 2.3–2.4 if resources allow
- **If blocked:** Check the dependency graph above — every step depends on its predecessor
