# North Star Program Definition

**Date:** April 6, 2026  
**Baseline:** `baseline-north-star-v0`

This document defines what mercury is optimizing for. It guides architectural decisions, code reviews, and meta-agent evolution proposals.

---

## Core Thesis

Mercury is a customized fork of `nous-research/hermes-agent` optimized for **tight-leash autonomous agent execution** with **hierarchical episodic memory** and **score-driven self-improvement**.

The agent operates on a principle: **small, measurable wins through structured iteration**, not speculative feature accumulation.

---

## Optimization Axes

### 1. Memory Efficiency & Retrieval Latency

**Metric:** Tokens-per-query vs. response quality (F1, BLEU, task success rate)

**Target:** xMemory architecture achieving 39%+ token reduction without F1 regression

**Why:** Context is the bottleneck on consumer hardware (32GB VRAM, AMD R9700). Every token saved in retrieval is a token freed for reasoning.

**Canaries:**
- Retrieve 100 messages from SessionDB, measure parse time + Claude latency
- Measure semantic/theme cluster coherence (prevent retrieval collapse)
- Track stage-I vs stage-II fallback rate (goal: <5% require stage II)

---

### 2. Interrupt Responsiveness

**Metric:** Latency from `_interrupt_requested=True` to actual thread yield

**Target:** <100ms (8 10ms checkpoints minimum, no blocking sleeps >100ms)

**Why:** User-facing agent must respond to stop commands instantly, not after a 5-second tool delay.

**Canaries:**
- Measure time.sleep() blocking duration across tool_delay, retries, polling loops
- Identify any sleep() > 100ms without interrupt checking
- Benchmark interrupt latency under load (multiple concurrent tool calls)

---

### 3. Security Boundary Integrity

**Metric:** Exploit attack surface: code injection, path traversal, privilege escalation

**Target:** Zero injectable code paths in subprocess execution, file I/O, YAML parsing

**Why:** Agent executes user-provided code and config. One injection = full system compromise.

**Canaries:**
- All subprocess.Popen() wrapped with argument quoting (shlex.quote)
- YAML parsing via yaml.safe_load only
- File paths validated before use (no ../../../ escapes)
- Test suite includes injection-attempt cases

---

### 4. Self-Improvement Velocity

**Metric:** Iterations-to-better-performance for code changes, measured via eval harness

**Target:** Regression-gated acceptance: only changes with measured improvement merge

**Why:** Without automated eval, harness drift is inevitable. Meta-agent needs quantified feedback.

**Canaries:**
- 5-10 canonical eval cases exist (harbor task format: test.sh → 0.0–1.0 score)
- Baseline scores established for each case
- Failed proposals logged with reason (regression, no improvement, timeout)

---

### 5. Architecture Simplicity

**Metric:** Indirection layers between intent and execution

**Target:** <3 layers of abstraction for any user-facing code path

**Why:** More layers = more surface area for bugs, harder to debug, slower iteration.

**Canaries:**
- Agent receives intent → directly routes to handler (no middleware chains)
- Memory retrieval is two-stage (semantic→episode), not N-stage
- Sandboxing is syscall-level (seccomp), not wrapper-upon-wrapper

---

## Known Failure Modes

### Memory Coherence Degradation
**Problem:** xMemory theme/semantic clusters diverge from actual usage over time (concept drift)  
**Early sign:** Retrieval F1 drops >5% without data change  
**Mitigation:** Karpathy health check cron (weekly) flags stale nodes, suggests recompilation

### Interrupt Checking Blind Spots
**Problem:** A code path bypasses `self._interrupt_requested` check, blocks shutdown  
**Early sign:** `kill -TERM` takes >5s to exit, user complaint  
**Mitigation:** Add interrupt-latency test to CI, measure blocking call chains

### Subprocess Injection (Regression)
**Problem:** New code adds subprocess call without shlex.quote()  
**Early sign:** Security scanner finds unquoted variables in subprocess strings  
**Mitigation:** Pre-commit hook or linter rule (ruff plugin?) to flag raw f-strings in subprocess

### Eval Harness Overfitting
**Problem:** Agent optimizes for test cases, regresses on real usage  
**Early sign:** High test scores but user reports poor real-world performance  
**Mitigation:** Canonical cases should represent diverse intents, update quarterly based on failure logs

---

## Active Experiments

| Experiment | Status | Goal | Success Metric |
|-----------|--------|------|-----------------|
| xMemory Stage I/II retrieval | In design | Replace flat retrieval with hierarchical | F1 ≥45%, latency <5s |
| Interruptible sleep checkpoints | Done | Responsive interrupts | Interrupt latency <100ms |
| Command injection hardening | Done | Zero subprocess injections | All tests pass, no escapes found |
| Audit log schema | Pending design | Failure clustering → eval cases | 5+ distinct failure patterns identified |
| Sandboxing (bwrap/seccomp) | Pending design | Contain subprocess execution | All execs constrained to /tmp, no file escape |

---

## Evaluation & Gating

Every proposed change (from Jules or human) goes through:

1. **Code review:** Does it move toward one of the 5 optimization axes?
2. **Canonical eval:** Run 5-10 test cases, must not regress baseline
3. **Failure log:** If change fails, log it with reason (used for clustering)
4. **Merge:** Only accept if (review ✓) AND (eval ✓)

Rejected proposals don't disappear — they're logged in `proposals/` directory with reason. Future iterations may resurrect them if context changes.

---

## Quarterly Reviews

**Every 3 months:**
- Rerun all canonical eval cases, update baselines
- Review failure logs, cluster by pattern (memory, interrupt, security, eval)
- Adjust optimization axes weights if real-world data suggests different priority
- Archive old proposals, assess which deferred ideas are now viable

---

## References

- xMemory paper: hierarchical retrieval, 39% token reduction, F1 +3.53
- NeoSigma: failure → eval → gated acceptance loop
- Karpathy KB: episodic memory health checks, wiki synthesis
- OpenShell: subprocess isolation via bwrap/seccomp
