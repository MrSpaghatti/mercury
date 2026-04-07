# Next Session Plan: Roadmap & Priorities

**Current Date:** 2026-04-06  
**Last Completed:** Phase 4.1 (News/Infosec Digest) — commit a3d14725  
**Status:** All Phase 2 work complete (audit_log, xMemory, sandboxing, canonicals, baselines)  

---

## Executive Summary

The Hermes agent now has:
- ✅ **Core infrastructure:** Session DB, audit logging, episodic memory (xMemory), subprocess sandboxing
- ✅ **Self-improvement loop:** 5-10 canonical eval cases with baseline scores, regression testing passes
- ✅ **News pipeline:** HackerNews + arXiv + CISA KEV with ModelProvider abstraction for flexible inference

**Next priorities** (in recommended order):
1. **Phase 2.6:** Failure clustering (analyze 7 days of audit_log, identify patterns, generate new eval cases)
2. **Phase 4.2:** Homelab health alerts (monitor 6 core services, push Telegram alerts on anomalies)
3. **Phase 3.1:** Evolution proposals (automated paper discovery → relevance filter → proposal generation → human gate)

---

## Phase 2.6: Failure Clustering (HIGHEST PRIORITY)

**Why:** Closes the feedback loop. Once we have real failure data from audit_log, we can:
- Identify patterns (e.g., "memory retrieval fails 3x when history >100 messages")
- Generate new eval cases from novel patterns
- Feed findings back to 3.1 (evolution proposals) for autoagent acceptance

**Status:** Script skeleton exists (`scripts/failure_clustering.py`), needs implementation.

**Effort:** ~2-3 hours

**Tasks:**

1. **Implement `scripts/failure_clustering.py`:**
   - Query audit_log for last 7 days
   - Group by (intent_category, failure_reason)
   - Find top 5-10 patterns
   - For patterns with count >= 3, generate eval case stub in `tests/canonicals/`
   - Output human-readable report to `logs/failure_clusters_YYYY-MM-DD.md`

2. **Run clustering weekly:**
   - Add cron job to jobs.json (e.g., Sundays 02:00)
   - Store reports in `logs/` for trend tracking

3. **Wire findings into 3.1:**
   - Mark novel patterns with "needs_eval_case" flag
   - Evolution proposals can reference these patterns as motivation

**Success criteria:**
- [ ] Script runs without errors
- [ ] Identifies 3-5 distinct failure patterns
- [ ] Each pattern has count, affected sessions, sample errors
- [ ] New eval cases generated for patterns with count >= 3
- [ ] Report is human-readable and actionable

---

## Phase 4.2: Homelab Health Alerts

**Why:** Proactive monitoring of local services. Complements digest (external signal) with internal state.

**What:** Monitor Headscale, Gitea, Vaultwarden, ChromaDB, SearXNG, FastAPI endpoints.

**Design:**
- Simple HTTP GET + timeout checking
- SQLite state table for trend detection (latency spikes, up→down transitions)
- Telegram alerts on anomalies (service down, latency >5s)
- Daily "all green" summary

**Effort:** ~2 hours

**Tasks:**

1. **Create `scripts/homelab_monitor.py`:**
   - Poll 6 services every 5-10 minutes
   - HTTP GET with 5s timeout
   - Log response time to SQLite
   - Detect state changes (up→down, latency spike >50% increase)

2. **Add to hermes_state.py:**
   - New table: `homelab_status` (service, last_check, status, latency_ms)
   - Indexes on service name and last_check timestamp

3. **Create `scripts/homelab_alert.py`:**
   - Query `homelab_status` for recent anomalies
   - Send Telegram alerts (service down, latency warning)
   - Send daily "all green" at 06:00

4. **Wire to jobs.json:**
   - `homelab-check`: every 5 minutes
   - `homelab-alert`: daily at 06:00

**Success criteria:**
- [ ] Monitoring loop runs without hanging
- [ ] All 6 services checked on schedule
- [ ] Alerts sent within 30s of anomaly
- [ ] State transitions logged correctly
- [ ] Daily summary sent even if all green

---

## Phase 3.1: Evolution Proposals (STRATEGIC)

**Why:** Closes the outer feedback loop. External signal (papers) → relevance filter → proposal → eval gate → autoagent acceptance.

**What:** Automated paper discovery pipeline that generates proposals for architectural improvements.

**Scope:** Large. Break into sub-phases.

**Effort:** 4-6 hours

### 3.1.1: Daily Paper Poll (1h)

**Tasks:**
1. Cron job queries HuggingFace Papers API daily at 09:00 UTC
2. Store papers in SQLite alongside audit logs
3. Supplement with arXiv RSS, Papers With Code, HF Spaces trending

### 3.1.2: Haiku-Class Relevance Filter (1h)

**Tasks:**
1. Score each paper against ecosystem tags:
   - High weight: agent memory, RAG, tool-use, inference efficiency
   - Medium weight: self-improvement, meta-learning, routing
   - Negative: CUDA-only, needs >32GB VRAM, proprietary APIs
2. Hard gates: reject hardware-specific, benchmark-only, <2 weeks old (no code)
3. Output: candidate papers above 0.6 threshold

### 3.1.3: Sonnet-Class Applicability Analyzer (1h)

**Tasks:**
1. Read abstract + methodology section
2. Map to current components (memory, routing, sandboxing, model, retrieval)
3. Estimate effort (hours), expected metric delta
4. Generate proposal markdown

### 3.1.4: Human Review Gate (0.5h)

**Tasks:**
1. Telegram notification with paper title + proposal summary
2. User can approve/reject/defer via reactions or buttons
3. Approved → autoagent loop, rejected → logged with feedback

### 3.1.5: Autoagent Integration (1.5h)

**Tasks:**
1. Meta-agent reads approved proposal + BACKLOG.md
2. Implements change in isolated branch
3. Runs canonical eval suite
4. Accepts if score ≥ baseline, rejects if regression
5. Logs outcome to `results.tsv`

**Key requirement:** Use ModelProvider abstraction for all inferences (Haiku for filter, Sonnet for analyzer). This is critical for post-R9700 cost savings.

---

## Implementation Roadmap (Recommended Order)

```
Phase 2.6 (Failure Clustering)
  ↓ (analyze real audit data)
Phase 4.2 (Homelab Health Alerts)
  ↓ (parallel: gathering feature requests)
Phase 3.1 (Evolution Proposals)
  ↓ (closes feedback loop: external signal → internal improvement)
Phase 4.3 (Obsidian Vault Read Access)
  ↓
Phase 4.4 (Model Spend Tracking)
  ↓
... iterate
```

**Rationale:**
- 2.6 first: Unblocks 3.1 (need failure clustering to tune proposal filters)
- 4.2 parallel: Independent, adds value to monitoring/alerting
- 3.1 next: Closes loop, enables continuous self-improvement

---

## Code Quality Standards

When implementing, follow these principles (from program.md):

### 1. Memory Efficiency & Retrieval Latency
- Measure tokens-per-query vs response quality
- Aim for 39%+ token reduction without F1 regression
- Track stage-I vs stage-II fallback rate (<5% should require stage II)

### 2. Interrupt Responsiveness
- All blocking operations must have <100ms checkpoints
- No sleep() > 100ms without interrupt checking
- Benchmark interrupt latency under load

### 3. Security Boundary Integrity
- All subprocess calls quoted with shlex.quote()
- YAML parsed with yaml.safe_load only
- File paths validated (no ../ escapes)
- Test suite includes injection-attempt cases

### 4. Self-Improvement Velocity
- Every proposed change gated by eval harness
- Baseline scores immutable (baseline_scores.json)
- Failed proposals logged with reason
- New failure patterns → new eval cases

### 5. Architecture Simplicity
- <3 indirection layers for any user-facing code path
- Memory: 2-stage (semantic→episode), not N-stage
- Sandboxing: syscall-level (seccomp), not wrapper-upon-wrapper

---

## Environment Setup

Before starting next session:

```bash
# Clone repo
git clone https://github.com/MrSpaghatti/mercury.git
cd mercury

# Install deps
pip install -r requirements.txt
# or: uv sync (if using uv)

# Check schema version
python3 -c "from hermes_state import SessionDB; db = SessionDB(); print(f'Schema: {db._conn.execute(\"SELECT version FROM schema_version\").fetchone()[0]}')"
# Should print: Schema: 8

# List files from Phase 4.1
ls -la scripts/digest_*.py config/digest_sources.json agent/model_provider.py

# Run a quick sanity check
python3 << 'EOF'
from hermes_state import SessionDB
db = SessionDB()
cursor = db._conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='digest_items'")
print(f"digest_items table: {bool(cursor.fetchone()[0])}")
cursor = db._conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='audit_log'")
print(f"audit_log table: {bool(cursor.fetchone()[0])}")
db.close()
EOF
```

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `hermes_state.py` | SQLite schema, session storage, FTS5 search |
| `agent/model_provider.py` | Flexible model inference (local or remote) |
| `agent/xmemory/stack.py` | Episodic memory retrieval (already implemented) |
| `scripts/digest_*.py` | News/infosec digest pipeline |
| `scripts/failure_clustering.py` | Failure pattern analysis (skeleton only) |
| `run_agent.py` | Main agent loop (do not modify without approval) |
| `jobs.json` | Scheduled task definitions |
| `BACKLOG.md` | Phase tracking and acceptance criteria |
| `program.md` | North Star optimization axes |
| `baseline_scores.json` | Immutable eval baseline (do not touch) |
| `tests/canonicals/` | 5-10 test cases defining correct agent behavior |

---

## Testing Strategy

For each new feature:

1. **Unit tests:** Test individual functions (fetch_hackernews, score_text, etc.)
2. **Integration tests:** Test pipeline end-to-end with mock data
3. **Canonical regression:** Run canonical eval suite, verify no regression
4. **Failure clustering:** Analyze audit_log for new patterns
5. **Manual testing:** Run once manually, verify outputs

**Always run canonicals before committing:**
```bash
python3 -m pytest tests/canonicals/ -v
# All tests should PASS and scores should not regress >5% from baseline
```

---

## Git Workflow

```bash
# Create feature branch
git checkout -b phase-4.2/homelab-monitoring

# Implement and test
# ... make changes ...
python3 -m pytest tests/canonicals/ -v  # Verify no regression

# Commit with descriptive message
git commit -m "Phase 4.2: Implement homelab monitoring

- Add homelab_monitor.py script for 6 service checks
- Add homelab_status table to hermes_state.py v9
- Add homelab_alert.py for Telegram alerting
- Wire to jobs.json with 5-min check frequency
- All 6 services (Headscale, Gitea, Vaultwarden, ChromaDB, SearXNG, FastAPI) monitored

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push and create PR
git push origin phase-4.2/homelab-monitoring
# PR template will auto-populate
```

---

## Documentation Update Checklist

When completing a phase:

- [ ] Update BACKLOG.md with completion status and date
- [ ] Create PHASE_X.Y_HANDOFF.md with detailed implementation notes
- [ ] Update NEXT_SESSION_PLAN.md (this file) with new priorities
- [ ] Update README.md if user-facing features were added
- [ ] Add architecture notes to docs/ if appropriate
- [ ] Document any new env vars in .env.example
- [ ] Document any new tables in schema comments

---

## Troubleshooting

### SQLite schema migration fails
**Symptom:** "Schema version mismatch"  
**Fix:** Delete ~/.hermes/state.db and let it reinitialize (safe, session data not lost)

### ModelProvider initialization fails
**Symptom:** "OPENROUTER_API_KEY env var not set"  
**Fix:** Set either `LOCAL_MODEL_ENDPOINT` or `OPENROUTER_API_KEY` before running filter scripts

### Telegram messages not sending
**Symptom:** "Failed to send Telegram message"  
**Fix:** Verify TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set and valid

### Canonical eval regression
**Symptom:** Baseline test score dropped >5%  
**Fix:** Review changes, revert if necessary, investigate root cause before committing

---

## References

- **PHASE_4.1_HANDOFF.md** — Detailed Phase 4.1 implementation notes
- **BACKLOG.md** — Complete phase tracking
- **program.md** — North Star optimization axes (read before implementing)
- **ROADMAP.md** — Long-term vision and model tier strategy
- **hermes_constants.py** — Shared constants (URLs, model names, etc.)
- **baseline_scores.json** — Canonical eval baseline (immutable reference)

---

## Questions to Answer Before Next Session

1. **Priority:** Should Phase 2.6 (failure clustering) or Phase 4.2 (health alerts) be done first?
2. **Scope:** Should Phase 3.1 (evolution proposals) use cached papers or live polling?
3. **Model strategy:** For Phase 3.1, should Sonnet analyzer use OpenRouter or wait for local 32B model?
4. **Homelab services:** Any services other than the 6 listed (Headscale, Gitea, Vaultwarden, ChromaDB, SearXNG, FastAPI) to monitor?
5. **Telegram rate limits:** Do we need to batch alerts or handle DDoS-prevention limits?

---

## Success Metrics (Long-term)

After Phase 3.1 complete:
- [ ] Self-improvement loop closes: failures → eval cases → proposals → acceptance
- [ ] 5+ new proposals generated from papers, 2+ accepted
- [ ] Canonical scores improve by 3-5% from accepted proposals
- [ ] No security regressions (all injection tests still passing)
- [ ] Memory retrieval F1 stays ≥45%, latency <5s
- [ ] Interrupt latency <100ms under load

---

## Summary for Next Session

**You're picking up from:** Phase 4.1 complete (digest pipeline), Phase 2 complete (eval harness + audit)

**Priority path:**
1. Phase 2.6: Failure clustering (closes internal feedback loop)
2. Phase 4.2: Homelab alerts (adds monitoring)
3. Phase 3.1: Evolution proposals (closes external feedback loop)

**Key insight:** Phase 2.6 unblocks 3.1, and 3.1 is the crown jewel—it enables true self-improvement.

**Status:** All infrastructure in place. Ready to iterate.

Good luck! Questions? Check BACKLOG.md, program.md, and PHASE_4.1_HANDOFF.md.
