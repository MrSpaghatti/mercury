# Critical Audit Findings - Action Required

## CRITICAL Issue #1: Session Message Duplication/Loss

**Severity:** CRITICAL  
**Status:** Requires Immediate Fix  
**Risk:** Data Loss

### Problem Location

**File:** `/home/spag/mercury/cli.py:4985-4987`
```python
if self.agent is not None:
    try:
        self.agent._persist_session(
            self.conversation_history,
            self.conversation_history,  # ← BUG: Same value twice
        )
```

**Function Signature:** `/home/spag/mercury/run_agent.py:1711`
```python
def _persist_session(self, messages: List[Dict], conversation_history: List[Dict] = None):
```

**Affected Logic:** `/home/spag/mercury/run_agent.py:1743-1745`
```python
start_idx = len(conversation_history) if conversation_history else 0
flush_from = max(start_idx, self._last_flushed_db_idx)
for msg in messages[flush_from:]:  # ← Could skip or duplicate messages
```

### Root Cause
The second parameter to `_persist_session` is meant to represent the pre-compression conversation state (from a previous session after splitting). It should NOT be the same as `messages`. When both are identical:

1. `start_idx` = length of all messages (wrong - should be previous session's count)
2. `flush_from` = max of wrong start_idx and last flushed index
3. Messages are either duplicated or skipped in SQLite persistence

This defeats the dedup logic mentioned in the comment at line 1729: `"preventing the duplicate-write bug #860"`

### Impact
- **Data Loss:** Messages may not be persisted to SQLite
- **Data Duplication:** If `flush_from` calculation is off, messages may be written twice
- **Silent Failure:** No error message - session appears to persist correctly

### Immediate Fix Required

#### Option A: Pass Correct Parameter
Determine what `conversation_history` should be:
- If this is the first session → pass `None`
- If this is a continuation after compression → pass the pre-compression message list
- If this parameter is unused → remove it

```python
# Example if conversation_history is not needed:
self.agent._persist_session(self.conversation_history)

# Example if conversation_history should be the old session's state:
self.agent._persist_session(
    self.conversation_history,
    self.previous_session_messages  # Track separately
)
```

#### Option B: Understand the Intent
Check git history for when this parameter was added:
```bash
git log -p -S "conversation_history" -- run_agent.py | head -200
```

### Verification Steps
1. Write a test that persists N messages, then calls `_persist_session` again with the same messages
2. Verify that SQLite has exactly N messages, not 2N or fewer
3. Check the `_last_flushed_db_idx` tracking is correct

---

## CRITICAL Issue #2: Unsafe asyncio.run() in Multi-threaded Context

**Severity:** CRITICAL  
**Status:** Requires Immediate Fix  
**Risk:** Vision Analysis Crashes

### Problem Location

**File:** `/home/spag/mercury/run_agent.py:4821-4823`
```python
def _materialize_data_url_for_vision(self, vision_source):
    # ... in _analyze_vision_image which is called from tool execution
    result_json = asyncio.run(
        vision_analyze_tool(image_url=vision_source, user_prompt=analysis_prompt)
    )
```

### Root Cause
`asyncio.run()` creates a new event loop and can only be called from the main thread. However, this code is called from `_execute_tool_calls_concurrent()` which runs in `ThreadPoolExecutor` worker threads (line 5659).

When a worker thread calls `asyncio.run()`, it raises:
```
RuntimeError: asyncio.run() cannot be called from a running event loop
```
or
```
RuntimeError: asyncio.run() failed to set up threads
```

### Impact
- **Critical Crash:** Vision analysis (image understanding) immediately fails
- **Unpredictable:** Only occurs when agent uses concurrent tool execution mode
- **Silent in Sequential Mode:** Works fine in sequential mode (single main thread)

### Immediate Fix Required

```python
# In _analyze_vision_image() method around line 4821

import asyncio
import threading

description = ""
try:
    from tools.vision_tools import vision_analyze_tool

    # Check if we're in a worker thread
    try:
        # Try asyncio.run() first (main thread path)
        result_json = asyncio.run(
            vision_analyze_tool(image_url=vision_source, user_prompt=analysis_prompt)
        )
    except RuntimeError as e:
        # If asyncio.run() fails due to thread context, try alternate approach
        if "cannot be called from a running event loop" in str(e) or "set up threads" in str(e):
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_json = loop.run_until_complete(
                    vision_analyze_tool(image_url=vision_source, user_prompt=analysis_prompt)
                )
            finally:
                loop.close()
        else:
            raise  # Re-raise if it's a different RuntimeError
    
    result = json.loads(result_json) if isinstance(result_json, str) else {}
    description = (result.get("analysis") or "").strip()
except Exception as e:
    description = f"Image analysis failed: {e}"
finally:
    if cleanup_path and cleanup_path.exists():
        try:
            cleanup_path.unlink()
        except OSError:
            pass
```

### Verification Steps
1. Set up agent to use concurrent tool execution (default)
2. Submit an image for analysis
3. Verify it completes without RuntimeError
4. Check that analysis result is populated correctly

---

## HIGH Issue #3: Duplicate Dead Code Block

**Severity:** HIGH  
**Status:** Requires Fix  
**Risk:** Code Confusion, Maintenance Burden

### Problem Location

**File:** `/home/spag/mercury/cli.py:5507-5512`
```python
# Line 5507-5512 in _clarify_with_timeout() method
if now - _last_countdown_refresh >= 5.0:
    _last_countdown_refresh = now
    self._invalidate()
if now - _last_countdown_refresh >= 5.0:  # ← DUPLICATE: Always False after first block
    _last_countdown_refresh = now
    self._invalidate()
```

### Root Cause
After the first `if` block executes:
1. `_last_countdown_refresh` is set to `now`
2. The second `if` condition `now - _last_countdown_refresh >= 5.0` will be False (diff is ~0)
3. The second block never executes

This is dead code that appears to have been copied by mistake.

### Impact
- **Dead Code:** Second refresh never happens
- **Maintenance:** Confuses future developers, suggests intent may be missing
- **Bug Potential:** If the second block was meant to do something different, it's lost

### Immediate Fix Required

```python
# Option 1: Remove duplicate
if now - _last_countdown_refresh >= 5.0:
    _last_countdown_refresh = now
    self._invalidate()

# Option 2: If second block was meant to be different
if now - _last_countdown_refresh >= 5.0:
    _last_countdown_refresh = now
    self._invalidate()
# Remove the duplicate entirely
```

Check git blame to see why this was added:
```bash
git blame -L 5507,5512 cli.py
```

---

## HIGH Issue #4: 229+ Overly Broad Exception Handlers

**Severity:** HIGH  
**Status:** Systematic Refactoring Needed  
**Risk:** Masks bugs, complicates debugging

### Problem Summary

**Distribution:**
- `run_agent.py`: 92 instances of `except Exception`
- `cli.py`: 133 instances of `except Exception`
- `hermes_state.py`: 4 instances

### Example (run_agent.py:284)

```python
try:
    function_args = json.loads(tool_call.function.arguments)
except Exception:  # ← Too broad
    logging.debug("Could not parse args...")
    return False
```

**Problems:**
1. `json.JSONDecodeError` is expected - catch it specifically
2. `AttributeError` (if `tool_call.function` is None) is a bug - should crash
3. Other errors are unknown - handler hides them

### Immediate Fix Required - Start with Critical Paths

#### Path 1: Tool Call Argument Parsing
**Files:** run_agent.py (multiple locations)

```python
# Before
try:
    function_args = json.loads(tool_call.function.arguments)
except Exception:
    logging.debug(...)
    return False

# After
try:
    function_args = json.loads(tool_call.function.arguments)
except json.JSONDecodeError:
    logging.debug(
        "Could not parse args for %s — defaulting to sequential",
        tool_call.function.name,
    )
    return False
except (AttributeError, TypeError) as e:
    # This indicates a real bug - the API changed or something is wrong
    logging.error(f"Unexpected error accessing tool_call.function: {e}")
    raise
```

#### Path 2: Session Database Operations
**File:** run_agent.py:1539-1544

```python
# Before
except Exception as e:
    logger.warning("Session DB compression...")

# After
except sqlite3.OperationalError as e:
    logger.warning("Session DB locked: %s", e)
except (ValueError, TypeError) as e:
    logger.error("Invalid data for session DB: %s", e)
except Exception as e:
    logger.error("Unexpected session DB error: %s", e)
```

### Rollout Plan

1. **Week 1:** Fix 15 high-traffic paths (use code coverage to identify)
2. **Week 2:** Fix 30 remaining critical paths
3. **Week 3:** Systematic refactoring of remaining instances
4. **Add Linting:** Configure Pylint/Flake8 to warn on bare/broad `except`

---

## Summary: Critical Fixes Required

| Issue | File | Lines | Impact | Effort | Timeline |
|-------|------|-------|--------|--------|----------|
| Session Persistence | cli.py | 4985-4987 | DATA LOSS | 1-2 days | IMMEDIATE |
| asyncio.run() Threads | run_agent.py | 4821-4823 | VISION CRASH | 2-3 days | IMMEDIATE |
| Duplicate Code | cli.py | 5507-5512 | CONFUSION | 1 hour | This week |
| Broad Exceptions | Multiple | 229 instances | DEBUGGING HARD | 2-3 weeks | Sprint |

---

## Testing After Fixes

### Test 1: Session Persistence
```python
def test_session_persistence_no_duplication():
    """Verify messages aren't duplicated or lost during persistence."""
    agent = AIAgent(...)
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(100)]
    agent._persist_session(messages)
    agent._persist_session(messages)  # Call again
    
    # Verify SQLite has exactly 100 messages, not 200
    db_messages = agent._session_db.get_session_messages(agent.session_id)
    assert len(db_messages) == 100
```

### Test 2: Concurrent Vision Analysis
```python
def test_vision_analysis_concurrent():
    """Verify vision analysis works in concurrent mode."""
    agent = AIAgent()
    # Use concurrent execution mode
    messages = [{"role": "user", "content": "Analyze this image", "image": "..."}]
    # Should not raise RuntimeError
    response = agent.run_conversation_with_messages(messages)
    assert "vision" not in response.lower() or "analysis" in response.lower()
```

### Test 3: Exception Specificity
```python
def test_malformed_tool_args_specific_handling():
    """Verify malformed tool args are handled correctly."""
    # Should log but continue
    tool_call = Mock(function=Mock(arguments="{ invalid json }"))
    result = agent._try_tool_call(tool_call)
    # Should NOT raise, should return False or default
```
