# North Star Implementation Roadmap

**Baseline:** `baseline-north-star-v0` (commit 214f2da8)  
**Program:** `program.md` — defines optimization axes and gating criteria  

---

## Phase 1: Foundation (In Progress)

### ✅ Done
- [x] `program.md` — North Star optimization axes + success metrics + known failure modes
- [x] Merge baseline changes (xmemory scaffold, security/perf fixes, code cleanup)
- [x] 10 Jules sessions: code health, security hardening, interrupt responsiveness

### 🔄 In Flight (Jules Sessions)

| Priority | Task | Jules ID | Status | ETA |
|----------|------|----------|--------|-----|
| 3.1 | Implement audit_log table in hermes_state.py | 13652758914226909608 | ✅ Completed | 77b3efea |
| 3.2 | xMemory Stage I/II retrieval in stack.py | 5783766652620636935 | ✅ Completed | 36be14a8 |
| 3.3 | Subprocess sandboxing (bwrap/seccomp) | 1952571512354332496 | In Progress | — |
| 3.4 | Memory health check cron script | 5136199449893976380 | ✅ Completed | 36be14a8 |

### 📋 Phase 2: Eval Harness & Integration (Correct Sequencing)

**Critical:** Must follow this order. Baselines come *before* instrumentation.

- [ ] **2.1 Define canonical eval cases** (5-10 test cases)
  - Format: `tests/canonicals/test_*.py` (harbor-style: intent → expected tool/output)
  - Cases cover: tool_routing, memory_retrieve, intent_parse, injection_prevention, timeout_handling
  - Example: "retrieve relevant context from 10-message history" (F1≥0.7 = pass)
  
- [ ] **2.2 Manual baseline scoring** (run each case once, record 0.0–1.0 score)
  - Create `evals/baseline_scores.json` with canonical case scores
  - This is the reference frame — don't skip this
  
- [ ] **2.3 Integrate audit_log into run_agent.py** (hook at decision points)
  - Before tool call: `audit.log_tool_execution(session_id, tool_name=...)`
  - After tool call: log success/failure/timeout
  - In memory retrieve: `audit.log_memory_retrieve(session_id, memory_hit=...)`
  - In intent parse: `audit.log_decision(session_id, intent_category=...)`
  
- [ ] **2.4 Wire xMemory into session flow**
  - On session init: `xmem = XMemoryStack(db_path, chroma_path)`
  - After each agent turn: `xmem.store_interaction(user_id, user_msg, agent_response)`
  - In prompt building: `context = xmem.build_context(user_id, current_message)` → include in system prompt
  
- [ ] **2.5 Run canonicals against wired system** (compare to baseline)
  - Each case run 3 times (stability check)
  - Score must not regress vs baseline
  - If regression: identify why, fix, re-baseline
  
- [ ] **2.6 Implement failure clustering** (weekly batch analysis)
  - Query audit_log: group by (intent_category, failure_reason)
  - Top 5 patterns → new eval cases
  - Log to `logs/failure_clusters_YYYY-MM-DD.md`
  - **Important:** Run *after* 2.3–2.5 so audit_log has real data
  
- [ ] **2.7 Finish sandboxing** (bwrap/seccomp wrapper for exec tool)
  - Jules session 1952571512354332496 (currently in progress)
  - Once done: add to tool_routing decision path, verify injection attempts are blocked

---

## Phase 2: Meta-Agent Loop (Design Phase)

- [ ] Build evolution proposal pipeline (HF papers API polling)
- [ ] Implement autoagent hill-climbing loop (score-driven accept/reject)
- [ ] Carnice-style local 8B fine-tune (once real conversation data exists)

---

## Critical Path & Dependencies

### ⚠️ Key Blocking Rules
1. **Define eval baselines BEFORE instrumenting** — if you wire audit_log before knowing what "correct" is, you collect failure data with no reference frame
2. **xMemory is wired-only useful** — scaffolding is complete but zero data flows until `build_context()` is called from run_agent.py
3. **jobs.json is format reference, not live** — health check cron doesn't run until actual scheduler is active (systemd timer or Magpie)

### Sprint Sequencing (Next 2–3 Sessions)

**Sprint 1: Eval Harness (2.1–2.2)**
```
Define canonicals (2–4h) → Manual baseline scoring (1–2h)
→ Save baseline_scores.json → Use as reference for all future work
```

**Sprint 2: Integration (2.3–2.5)**
```
Wire audit_log (2–3h) → Wire xMemory (2–3h) → Run canonicals against wired system (1h)
→ Verify no regression vs baseline
```

**Sprint 3: Clustering + Evolution (2.6–2.7 + Phase 3)**
```
Failure clustering (2.6) → Autoagent loop (Phase 3)
(Only after audit_log has real data from 2.3–2.5)
```

### What NOT to do
- ❌ Wire audit_log before canonicals exist
- ❌ Run health check cron (it's dead until scheduler is live)
- ❌ Start autoagent loop before failure clustering is working
- ❌ Assume xMemory is live (it's scaffolded, not integrated)

---

## Optimization Axes Status

| Axis | Target | Current | Gap | Owner |
|------|--------|---------|-----|-------|
| Memory efficiency | 39% token ↓, F1≥45% | xMemory scaffolding live (not integrated) | Integration + baselines | 2.4 (wire into run_agent) |
| Interrupt responsiveness | <100ms latency | ✅ Done (interruptible sleep) | None | ✅ Shipped |
| Security boundary | Zero injections | 3 fixes merged, sandboxing pending | Finish bwrap wrapper | 2.7 (finish Jules 1952...) |
| Self-improvement velocity | Regression-gated | 0 eval cases yet | Canonicals + baselines | 2.1–2.2 (BLOCKER for rest) |
| Architecture simplicity | <3 abstraction layers | Unknown (need audit data) | Audit visibility | 2.3 (wire audit_log) |

---

## File Structure

```
mercury/
├── program.md                          ← ✅ North Star program definition
├── ROADMAP.md                          ← This file
├── HANDOFF.md                          ← ✅ Session handoff summary
├── docs/
│   └── AUDIT_LOG_SCHEMA.md            ← ✅ Audit log design + implementation notes
├── agent/
│   └── xmemory/
│       └── stack.py                   ← ✅ Full xMemory impl (EpisodeMemory, Semantic, Theme, Stack)
├── tools/
│   ├── sandbox.py                     ← 🔄 Sandboxing executor (Jules in progress)
│   ├── transcription_tools.py         ← ✅ Command injection fix
│   └── transcription_tools.py         ← ✅ Command injection fix
├── tools/environments/
│   └── docker.py                      ← ✅ Command injection fix
├── hermes_state.py                    ← ✅ audit_log table + migration + AuditLog class
├── run_agent.py                       ← ✅ Interruptible sleep, ⏳ pending: audit/xMemory wiring
├── scripts/
│   └── memory_health_check.py         ← ✅ Weekly cron script (not yet scheduled)
├── jobs.json                          ← ✅ Cron config (format reference, not live)
├── tests/
│   └── canonicals/                    ← ⏳ Eval cases (needs 2.1)
└── evals/
    └── baseline_scores.json           ← ⏳ Baseline reference (needs 2.2)
```

---

## Success Criteria (North Star Program)

### By EOQ (end of quarter)
- [ ] ✅ Scaffolding complete: program.md, audit_log, xMemory, health check
- [ ] **2.1–2.2:** 5-10 canonical eval cases + baseline scores (BLOCKER for everything else)
- [ ] **2.3:** Audit_log wired into run_agent.py, collecting real failure data
- [ ] **2.4:** xMemory wired into session flow (store_interaction, build_context in prompts)
- [ ] **2.5:** Canonicals re-run against wired system, zero regression vs baseline
- [ ] **2.6:** Failure clustering working, identifying top 5 patterns weekly
- [ ] **2.7:** Sandboxing live (bwrap/seccomp), zero filesystem escapes
- [ ] Health check cron configured (jobs.json) + scheduler activated

### By EOY
- [ ] Autoagent loop: proposed changes gated on eval scores
- [ ] Evolution proposals: HF papers API polling + relevance filtering active
- [ ] Carnice-style 8B fine-tune: trained on accumulated conversation data
- [ ] All 5 optimization axes showing measured improvement:
  - Memory efficiency: ≥39% token reduction, F1≥45%
  - Interrupt responsiveness: <100ms latency (verify under load)
  - Security boundary: zero injection escape attempts in audit log
  - Self-improvement velocity: autoagent loop accepting/rejecting changes
  - Architecture simplicity: audit_log reveals bottlenecks, <3 abstraction layers

---

## Critical Implementation Notes

### Blocking Order (Do Not Skip or Reorder)
1. **2.1–2.2 (Eval canonicals + baseline)** — These define "correct" behavior. Everything after depends on them.
2. **2.3 (Audit_log wiring)** — Must come before you expect audit data. Instrumenting without baselines is blind.
3. **2.4 (xMemory wiring)** — Scaffolding exists but is dead code until integrated into session flow.
4. **2.5 (Regression test)** — Verify wiring doesn't break anything.
5. **2.6 (Failure clustering)** — Only has signal once 2.3–2.5 are done.

### Dead Code (Waiting for Integration)
- `XMemoryStack` class fully implemented but never called from anywhere
- `AuditLog` helper class fully implemented but no calls in run_agent.py
- `jobs.json` exists but cron is not live (scheduler not active)
- `memory_health_check.py` runs standalone but no scheduled execution yet

### Reference Points for Next Session
- HANDOFF.md: what was completed, integration gaps, how to resume
- program.md: the "why" — optimization objectives
- docs/AUDIT_LOG_SCHEMA.md: instrumentation points in run_agent.py
- ROADMAP.md (this file): execution order and what's blocked on what
