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

### 📋 Next (Pending Jules)
- [ ] Integrate audit_log into run_agent.py (hook at tool routing, memory retrieve, intent parse)
- [ ] Eval case definitions (5-10 canonical test cases in harbor format)
- [ ] Regression test harness (baseline scoring, gate new changes)
- [ ] Failure clustering script (weekly analysis of audit logs)

---

## Phase 2: Meta-Agent Loop (Design Phase)

- [ ] Build evolution proposal pipeline (HF papers API polling)
- [ ] Implement autoagent hill-climbing loop (score-driven accept/reject)
- [ ] Carnice-style local 8B fine-tune (once real conversation data exists)

---

## Optimization Axes Status

| Axis | Target | Current | Gap | Owner |
|------|--------|---------|-----|-------|
| Memory efficiency | 39% token reduction, F1≥45% | Scaffolding only | xMemory impl | Jules (in progress) |
| Interrupt responsiveness | <100ms latency | Done (sleep checkpoints) | None | ✅ Merged |
| Security boundary | Zero injection paths | 3 fixes merged | Sandboxing | Jules (in progress) |
| Self-improvement velocity | Regression-gated acceptance | 0 eval cases yet | Audit + evals | Jules (in progress) |
| Architecture simplicity | <3 abstraction layers | Unknown (need audit) | Measure | Audit log will reveal |

---

## File Structure

```
mercury/
├── program.md                 ← North Star program definition
├── ROADMAP.md                 ← This file
├── docs/
│   └── AUDIT_LOG_SCHEMA.md   ← Audit log design (not yet implemented)
├── agent/
│   └── xmemory/
│       └── stack.py           ← Retrieval logic (scaffolding, needs impl)
├── tools/
│   ├── sandbox.py             ← Sandboxing executor (pending)
│   └── transcription_tools.py ← ✅ Command injection fix
├── tools/environments/
│   └── docker.py              ← ✅ Command injection fix
├── hermes_state.py            ← ✅ Fast JSON parsing, pending: audit_log table
├── run_agent.py               ← ✅ Interruptible sleep, pending: audit hooks
└── scripts/
    └── memory_health_check.py ← Health check cron (pending)
```

---

## Success Criteria (North Star Program)

### By EOQ (end of quarter):
- [ ] Audit log table live, 100+ entries from real usage
- [ ] xMemory retrieval live with F1≥40% on canonical cases
- [ ] Sandboxing live, zero filesystem escape attempts
- [ ] Karpathy health check running weekly, 3+ reports generated
- [ ] 5-10 canonical eval cases defined + baseline scores
- [ ] Failure clustering identifies top 5 issue patterns

### By EOY:
- [ ] Meta-agent loop accepting proposed changes on eval gates
- [ ] Evolution proposals (from HF papers API) feeding into loop
- [ ] Carnice-style fine-tune on accumulated conversation data
- [ ] All 5 optimization axes showing measured improvement

---

## Notes

- Jules tasks can run in parallel (background mode)
- Small fixes (import cleanup, doc updates) handled directly
- Architectural changes go through program.md + audit log gating
- All decisions logged in audit_log for future analysis
