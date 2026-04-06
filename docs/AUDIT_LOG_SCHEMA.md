# Audit Log Schema Design

**Purpose:** Track agent decision points and failures to enable failure clustering, eval case generation, and meta-agent learning.

**Status:** Design (not yet implemented in hermes_state.py)

---

## Core Table: `audit_log`

Extends `hermes_state.py` with a new table for tracking agent behavior and failure patterns.

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    timestamp REAL NOT NULL,
    
    -- Classification: what category of decision/action was this?
    intent_category TEXT NOT NULL,  -- 'tool_routing', 'memory_retrieve', 'intent_parse', 'result_format', etc.
    
    -- The specific operation
    operation TEXT,                  -- 'execute_tool', 'search_memory', 'classify_intent', 'call_model', etc.
    
    -- Tool/function executed (if applicable)
    tool_name TEXT,                 -- null if not tool-related
    
    -- Outcome
    severity TEXT NOT NULL,          -- 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    failure_reason TEXT,             -- null if success, else: 'timeout', 'injection_detected', 'wrong_tool', 'no_memory_hit', 'rate_limited', etc.
    
    -- Memory context
    memory_hit BOOLEAN DEFAULT 0,    -- Did retrieval find relevant context?
    memory_retrieved_count INTEGER,  -- How many messages/episodes were retrieved?
    memory_stage TEXT,               -- 'stage1_semantic', 'stage2_episode', 'none'
    
    -- User feedback (if any)
    user_feedback TEXT,              -- 'correct', 'incorrect', 'partial', null
    
    -- Structured context JSON
    context TEXT,                    -- {
                                     --   "input_intent": "user query",
                                     --   "chosen_tool": "tool_name",
                                     --   "tool_args": {...},
                                     --   "retrieved_context": [...],
                                     --   "response_time_ms": 250,
                                     --   "model_used": "claude-opus-4.5",
                                     --   "error_message": "...",
                                     -- }
    
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_intent ON audit_log(intent_category);
CREATE INDEX IF NOT EXISTS idx_audit_failure ON audit_log(failure_reason);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log(severity);
```

---

## Example Audit Log Entries

### Case 1: Successful tool routing
```json
{
  "session_id": "session-123",
  "timestamp": 1712345000.5,
  "intent_category": "tool_routing",
  "operation": "execute_tool",
  "tool_name": "search_code",
  "severity": "INFO",
  "failure_reason": null,
  "memory_hit": true,
  "memory_retrieved_count": 5,
  "memory_stage": "stage1_semantic",
  "user_feedback": null,
  "context": {
    "input_intent": "find all uses of function X",
    "chosen_tool": "search_code",
    "tool_args": {"query": "function X", "limit": 20},
    "retrieved_context": ["previous search used grep", "X is defined in module Y"],
    "response_time_ms": 150,
    "model_used": "claude-opus-4.5"
  }
}
```

### Case 2: Command injection detected (CRITICAL)
```json
{
  "session_id": "session-456",
  "timestamp": 1712345010.2,
  "intent_category": "tool_routing",
  "operation": "execute_tool",
  "tool_name": "run_command",
  "severity": "CRITICAL",
  "failure_reason": "injection_detected",
  "memory_hit": false,
  "memory_retrieved_count": 0,
  "memory_stage": null,
  "user_feedback": null,
  "context": {
    "input_intent": "run a command",
    "chosen_tool": "run_command",
    "tool_args": {"cmd": "test\"; echo hacked ; #"},
    "error_message": "Injection pattern detected in argument",
    "response_time_ms": 50,
    "model_used": "claude-opus-4.5"
  }
}
```

### Case 3: Memory retrieval missed context
```json
{
  "session_id": "session-789",
  "timestamp": 1712345020.7,
  "intent_category": "memory_retrieve",
  "operation": "search_memory",
  "tool_name": null,
  "severity": "WARNING",
  "failure_reason": "no_memory_hit",
  "memory_hit": false,
  "memory_retrieved_count": 0,
  "memory_stage": "stage1_semantic",
  "user_feedback": "incorrect",  -- user said: "I told you this last time"
  "context": {
    "input_intent": "retrieve context about API rate limits",
    "query_embedding": "...",
    "retrieved_count": 0,
    "expected_context": "API docs mention 100 req/min limit",
    "response_time_ms": 200
  }
}
```

---

## Instrumentation Points

Add audit log entries at these key decision points:

| Decision Point | Intent Category | Tool Name | Notes |
|---|---|---|---|
| Before tool routing | `tool_routing` | null | Which tool did the model choose? |
| Before tool execution | `tool_routing` | {tool_name} | Validate args, check for injection |
| After tool execution | `tool_routing` | {tool_name} | Success/timeout/error |
| Before memory retrieve | `memory_retrieve` | null | What query, what stage used |
| After memory retrieve | `memory_retrieve` | null | Hits/misses, relevance |
| Before intent parsing | `intent_parse` | null | Classify user input |
| After model call | `model_call` | null | Latency, completion tokens |
| Before response format | `result_format` | null | JSON validation, structure |

---

## Clustering Rules (for failure analysis)

Group audit entries by (intent_category, failure_reason, tool_name) to identify patterns:

```sql
SELECT
  intent_category,
  failure_reason,
  tool_name,
  COUNT(*) as count,
  COUNT(DISTINCT session_id) as sessions_affected
FROM audit_log
WHERE severity IN ('ERROR', 'CRITICAL')
  AND timestamp > datetime('now', '-7 days')
GROUP BY intent_category, failure_reason, tool_name
ORDER BY count DESC
```

**Output:** Top failure patterns become eval cases. E.g.:
- "tool_routing / wrong_tool / execute_tool" (47 occurrences, 12 sessions) → create eval: "does agent choose correct tool for task X?"
- "memory_retrieve / no_memory_hit / null" (23 occurrences, 8 sessions) → create eval: "does retrieval find relevant context?"

---

## Retention Policy

- Keep all ERROR/CRITICAL entries indefinitely
- Keep INFO/WARNING entries for 30 days
- Monthly archive: compress old logs, move to `audit_log_archive` table
- Retention can be adjusted based on database size

---

## Future Integration

Once this schema exists:
1. **Failure clustering script** (weekly): group by (intent_category, failure_reason), generate summary
2. **Eval case generator:** convert top clusters into concrete test cases
3. **Meta-agent feedback loop:** proposed changes must show improvement on these test cases
4. **Health check:** weekly report of new failure patterns

---

## Implementation Notes

- `context` should be JSON-serialized for flexibility (optional fields don't break schema)
- `timestamp` should use `time.time()` for consistent precision
- All instrumentation should be optional (if audit DB write fails, agent continues)
- Queries should use indices heavily (intent_category, failure_reason are hot)
- Consider batching writes if audit_log grows to 1M+ entries/week
