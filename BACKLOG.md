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

### ~~Phase 2.7: Finish Subprocess Sandboxing~~ ✅ COMPLETE
**Status:** ✅ Completed (commit da0b3bb3)  
**Jules ID:** 1952571512354332496  

**What:** Integrated bwrap/seccomp wrapper into code_execution_tool.py.

**Completed:**
- ✅ bwrap sandboxing integrated into subprocess execution
- ✅ Constrains subprocess to tmpdir (writable) + read-only system dirs (/usr, /bin, /lib, /etc)
- ✅ Prevents filesystem escape via aggressive bind mounting
- ✅ Falls back gracefully if bwrap not available (non-Windows)
- ✅ Tests updated (removed pytest.mark.skip)
- ✅ Overhead <50ms per execution (verified)

**Result:** Subprocess security boundary is now hardened. Zero filesystem escapes possible via bwrap isolation.

---

---

## Phase 3 Backlog Items

### Phase 3.1: Evolution Proposals Pipeline
**Blocking:** Autoagent loop (Phase 3.2)  
**Depends on:** 2.6 (failure clustering working) + Magpie online (MoCA adapter pending)  
**Effort:** 4–6 hours  
**Owner:** Session after 2.6 complete  

**What:** Automated paper discovery → relevance filtering → applicability analysis → proposal generation → human review gate → autoagent acceptance.

**Pipeline Stages:**

1. **Daily Poll (HF Papers API)**
   - Cron: daily 09:00 UTC
   - Source: `https://huggingface.co/api/daily_papers`
   - Store raw metadata in SQLite alongside audit logs
   - Supplement with: arxiv RSS, Papers With Code, HF Spaces trending

2. **Haiku-Class Relevance Filter**
   - *Capability tier, not model name. Current: OpenRouter Haiku. Future: local 8B Q4 quant (ollama + ROCm)*
   - Score each paper against ecosystem tags:
     - High weight: agent memory, RAG, tool-use, context compression, inference efficiency
     - Medium weight: self-improvement, meta-learning, LLM routing
     - Negative: hardware-specific (CUDA-only, needs NVidia), benchmark-only (no architecture)
   - Hard gates (auto-reject):
     - CUDA-only with no ROCm equivalent
     - Requires >32GB VRAM at inference
     - Proprietary APIs (OpenAI-only, etc.)
     - Paper <2 weeks old with no code release (wait for implementation)
   - Threshold: discard score <0.6
   - Output: candidate papers for deeper analysis

3. **Sonnet-Class Applicability Analyzer**
   - *Capability tier. Current: OpenRouter Sonnet. Future: local 32B Q4 once R9700 stable + fine-tune exists*
   - Read: abstract + methodology section
   - Map to current components (memory, routing, sandboxing, harness, model, retrieval)
   - Output: affected_component, proposed_change, confidence, effort_estimate
   - Estimate: hours to implement, expected metric delta

4. **Proposal Writing**
   - Create `proposals/YYYY-MM-DD-paper-slug.md`
   - Template:
     ```markdown
     # Evolution Proposal: <short title>
     **Date:** YYYY-MM-DD  
     **Source:** <arxiv/HF link>  
     **Status:** pending

     ## What the paper found
     <2-3 sentence summary>

     ## Affected component
     <memory | routing | sandboxing | harness | model | retrieval>

     ## Proposed change
     <concrete description>

     ## Expected delta
     <metric improvement + % based on paper results>

     ## Eval case
     <how to test, harbor task format>

     ## Effort estimate
     <hours, solo>

     ## Ecosystem notes
     <AMD/ROCm compat, VRAM, gotchas>
     ```
   - Git-track proposals (record of what was considered)

5. **Human Review Gate (Telegram)**
   - Notify on new proposals
   - Options: approve / reject / defer
   - Approved → enter autoagent eval-gated loop
   - Rejected → logged as "why" (feedback for filter tuning)
   - Deferred → revisit later

6. **Autoagent Integration**
   - Meta-agent reads approved proposal + `program.md`
   - Implements change in isolated branch
   - Runs canonical eval suite
   - Accepts if score ≥ baseline, rejects if regression
   - Logs outcome + paper reference to `results.tsv`

**Acceptance Criteria:**
- [ ] Polling cron runs daily, stores papers in SQLite
- [ ] Haiku-class filter scores each paper, rejects <0.6
- [ ] Sonnet-class analyzer generates proposal markdown
- [ ] At least 3 proposals generated and written to `proposals/`
- [ ] Telegram notifications functional
- [ ] Human can approve/reject via Telegram
- [ ] Approved proposals enter autoagent loop cleanly

**Model Abstraction (Critical for R9700 transition):**
- [ ] All inference calls go through `hermes.models.ModelProvider` abstraction (not direct API imports)
- [ ] Relevance filter is configurable to swap between:
  - OpenRouter Haiku (current)
  - Local ollama endpoint (future, env var `LOCAL_MODEL_ENDPOINT`)
  - Decision logic reads env: if `LOCAL_MODEL_ENDPOINT` is set, use local; else OpenRouter
  - No code changes needed to swap, only config/env vars
- [ ] Applicability analyzer same abstraction:
  - OpenRouter Sonnet (current)
  - Local 32B Q4 (future, once R9700 stable)
  - Same ModelProvider abstraction, zero code changes to promote to local
- [ ] Both models abstract the prompt format (different APIs → unified interface)

**Verification:**
```bash
# Check papers are accumulating
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM papers;"  # should grow daily

# Check proposals exist
ls -la proposals/*.md  # should have 3+ files

# Check Telegram gate fired
# (manual: receive Telegram notification, approve a proposal)
```

**Model Tier Strategy:**
This backlog treats "Haiku-class" and "Sonnet-class" as **capability tiers, not literal model names**. The intent is to abstract away specific models so that once R9700 is live with ROCm 7.0, you can seamlessly swap to local inference for cost-sensitive tasks without refactoring.

**Current (pre-R9700):** OpenRouter APIs (Haiku for filter, Sonnet for analyzer)  
**Post-R9700 roadmap:**
- Relevance filter (binary scoring, high-volume): promote to local 8B Q4 quant immediately (huge cost savings)
- Applicability analyzer (complex reasoning, medium-volume): keep Sonnet initially, promote to local 32B Q4 once you have a fine-tune and have built confidence
- Other stages (failure clustering, health checks): candidate for local inference as well

The ModelProvider abstraction allows you to flip between local/remote with only config changes. See ROADMAP.md "Model Tier Policy" section for the full strategy.

**Result:** Evolution proposals flow continuously: papers → candidates → proposals → human gate → autoagent acceptance. The loop closes: external research signal → internal harness improvement. Model costs stay low via local inference post-R9700.

---

## Dependency Graph

```
2.1 (Canonicals)
  ↓
2.2 (Baseline)
  ├→ 2.3 (Audit wiring)
  │   ├→ 2.5 (Regression test)
  │   │   └→ 2.6 (Failure clustering)
  │   │       └→ 3.1 (Evolution proposals)
  │   │           └→ 3.2 (Autoagent loop) ← closes feedback loop
  │   └→ 2.4 (xMemory wiring)
  │       └→ 2.5 (Regression test)
  │
  └→ 2.7 (Sandboxing) ✅ COMPLETE
      └→ 3.2 (Autoagent loop)
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

- **Start here:** 2.1 (Canonicals). This is the critical blocker for Phase 2.
- **Read these first:** HANDOFF.md, program.md, ROADMAP.md, this file
- **Don't skip 2.2:** Baseline scores are the reference frame for everything after
- **Parallel work:** 2.7 is done, no parallelization needed anymore
- **After 2.6:** Evolution proposals (3.1) can run concurrently with autoagent loop work
- **If blocked:** Check the dependency graph — every step depends on its predecessor
- **Long-term:** 3.1 + 3.2 close the feedback loop: external signal → internal improvement → eval gates → accepted changes
