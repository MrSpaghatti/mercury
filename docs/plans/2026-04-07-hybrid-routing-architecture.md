# Hybrid Supervisor/Worker/Escapement Architecture

This document outlines the architectural plan for a three-tier "Hybrid Supervisor/Worker" LLM routing system in Mercury. The goal is to maximize performance-per-dollar by utilizing local hardware for repetitive labor and high-level cloud models for reasoning and safety.

## 1. Architecture Overview

The system operates as a tiered hierarchy where tasks are delegated to the most cost-effective tier capable of handling them, with automatic escalation upon failure or complexity triggers.

### Tier 1: The Worker (Local Inference)
*   **Target Hardware:** ASRock Radeon AI PRO R9700 32GB (Local Node).
*   **Models:** Qwen 2.5 Coder 32B (via vLLM or Ollama).
*   **Role:** The "hands." This tier handles all deterministic tool calls (bash, file system, git), initial code drafting, and iterative debugging loops. It is the default entry point for sub-tasks.
*   **Cost:** Zero marginal cost (electricity only).

### Tier 2: The Supervisor (Cloud Reasoning)
*   **Endpoint:** OpenRouter.
*   **Models:** DeepSeek V3.2 / DeepSeek R1.
*   **Role:** The "brain." This tier performs high-level intent parsing, architectural planning, and complex debugging. It acts as the manager for the Worker, providing explicit step-by-step instructions. It does not execute tools directly unless planning requires a probe.
*   **Cost:** Sub-dollar frontier models (ultra-low cost cloud).

### Tier 3: The Escapement (Heavy Hitter Cloud)
*   **Endpoint:** Anthropic / Google Vertex / OpenRouter.
*   **Models:** Claude 4.6 Sonnet or Gemini 2.5 Pro.
*   **Role:** The "safety net." This tier is triggered only when the Worker/Supervisor loop fails to progress or hits a critical logic error. It possesses the highest reasoning capability to break out of complex "hallucination loops."
*   **Cost:** Premium (invoked only as a last resort).

---

## 2. State Machine & Routing Logic

The routing logic is governed by a state machine that tracks "Turn Context" and "Failure Counts."

### State Transitions

| Current State | Trigger | Next State | Action |
| :--- | :--- | :--- | :--- |
| **Idle** | User Request | **Supervisor** | Parse intent and generate execution plan. |
| **Supervisor** | Plan Generated | **Worker** | Delegate sub-task execution. |
| **Worker** | Success | **Supervisor** | Report result for next step planning. |
| **Worker** | N Consecutive Tool Failures | **Supervisor** | Escalate for plan revision/debugging. |
| **Worker** | Turn Count > Threshold | **Supervisor** | Escalate to prevent infinite loops. |
| **Supervisor** | M Consecutive Re-plans | **Escapement** | Final intervention for logic resolution. |

### Deterministic Triggers (Examples)
*   **N (Worker Failure Limit):** 3 consecutive tool errors (e.g., `bash` exit code non-zero with no progress).
*   **Max Worker Turns:** 10 turns per sub-task before checking back with Supervisor.
*   **Loop Detection:** If the last 3 tool calls are identical (arguments and tool), trigger Supervisor.

---

## 3. Configuration Schema

Proposed YAML structure for `routing_config.yaml` (or section in `cli-config.yaml`):

```yaml
routing:
  strategy: hybrid_supervisor_worker
  enabled: true
  
  tiers:
    worker:
      provider: local
      model: qwen2.5-coder:32b
      base_url: "http://localhost:11434" # Ollama/vLLM
      max_iterations: 10
      consecutive_failure_limit: 3
      
    supervisor:
      provider: openrouter
      model: deepseek/deepseek-r1
      api_key_env: OPENROUTER_API_KEY
      max_replans: 3
      
    escapement:
      provider: anthropic
      model: claude-3-5-sonnet-latest
      api_key_env: ANTHROPIC_API_KEY

  logic:
    prefer_local_tools: true
    auto_escalate_on_timeout: true
    fallback_threshold_seconds: 60
```

---

## 4. Implementation Phases

### Phase 1: Router Abstraction (Foundation)
- Refactor `agent/smart_model_routing.py` into a more robust `HybridRouter` class.
- Update `ModelProvider` to support tiered instantiation (keeping three clients active/warm).
- Implement the "State Tracker" to monitor turn counts and tool failure patterns.

### Phase 2: Supervisor Prompting (The Manager)
- Develop specialized system prompts for the **Supervisor** tier that focus on *delegation* rather than *execution*.
- Ensure the Supervisor outputs structured plans that the **Worker** can parse as distinct sub-goals.

### Phase 3: Loop Integration (The Engine)
- Modify `environments/agent_loop.py` to handle the hand-off between Supervisor and Worker.
- Implement the "context window compression" strategy: when escalating to Supervisor, send a summary of Worker attempts rather than the full raw tool output to save cloud tokens.

### Phase 4: Validation & Fallback (The Safety)
- Implement the **Escapement** trigger logic.
- Add telemetry to track how often escalation occurs (ROI monitoring).
- Verify FOSS-first integration by ensuring the system functions with `local` + `OpenRouter` only (Escapement disabled by default).
