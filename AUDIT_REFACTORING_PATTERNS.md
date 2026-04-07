# Refactoring Patterns for Audit Findings

This document provides before/after code examples for systematic refactoring of identified issues.

---

## Pattern 1: Replace Broad Exception Handlers with Specific Ones

### Problem
```python
except Exception:
    logger.debug("Failed to parse")
    return None
```

**Issues:**
- Hides real bugs (AttributeError, TypeError)
- Makes debugging difficult
- Doesn't distinguish expected failures from unexpected ones

### Solution Pattern

```python
# Pattern A: Expected single exception
try:
    result = json.loads(data)
except json.JSONDecodeError:
    logger.debug("Invalid JSON, continuing")
    return None

# Pattern B: Multiple expected exceptions
try:
    config = load_config()
except FileNotFoundError:
    logger.info("Config file not found, using defaults")
    config = DEFAULT_CONFIG
except json.JSONDecodeError as e:
    logger.error("Config file is malformed: %s", e)
    raise

# Pattern C: Expected exceptions + unexpected fallback
try:
    token = refresh_token(old_token)
except ConnectionError as e:
    logger.warning("Network error, retrying: %s", e)
    return None  # Caller should retry
except json.JSONDecodeError as e:
    logger.error("Invalid token response: %s", e)
    raise
except Exception as e:
    # Catch unexpected errors for logging
    logger.exception("Unexpected error refreshing token: %s", e)
    raise
```

### Locations to Fix (Priority Order)

1. **run_agent.py:284** - JSON parsing in tool calls
   ```python
   # Before
   except Exception:
       logging.debug("Could not parse args...")
       return False
   
   # After
   except json.JSONDecodeError:
       logging.debug("Could not parse args for %s", tool_name)
       return False
   except (AttributeError, TypeError) as e:
       logging.error("Invalid tool_call structure: %s", e)
       raise
   ```

2. **run_agent.py:907-908** - API error handling
   ```python
   # Before
   except Exception as e:
       logger.warning("API call failed...")
   
   # After
   except httpx.TimeoutException:
       logger.warning("API timeout, will retry")
   except httpx.HTTPStatusError as e:
       if e.response.status_code == 429:
           logger.warning("Rate limited")
       else:
           logger.error("API error: %s", e)
   except Exception as e:
       logger.exception("Unexpected API error: %s", e)
   ```

3. **run_agent.py:1539** - Database operations
   ```python
   # Before
   except Exception as e:
       logger.warning("Session DB...")
   
   # After
   except sqlite3.OperationalError as e:
       if "locked" in str(e):
           logger.debug("DB locked, retrying")
       else:
           logger.error("DB operational error: %s", e)
   except sqlite3.IntegrityError as e:
       logger.error("Data integrity violation: %s", e)
   except Exception as e:
       logger.exception("Unexpected DB error: %s", e)
   ```

---

## Pattern 2: Add Validation for Unsafe Operations

### Problem
```python
_model_short = self.model.split("/")[-1] if "/" in self.model else self.model
```

**Issues:**
- Assumes `self.model` is a string
- No bounds checking
- Will fail if `self.model` is None

### Solution Pattern

```python
# Pattern A: Type checking first
if isinstance(self.model, str):
    _model_short = self.model.split("/")[-1] if "/" in self.model else self.model
else:
    _model_short = str(self.model) if self.model else "unknown"

# Pattern B: Try/except for robustness
try:
    if "/" in str(self.model):
        _model_short = str(self.model).split("/")[-1]
    else:
        _model_short = str(self.model)
except (TypeError, AttributeError):
    _model_short = "unknown"

# Pattern C: Dedicated validation function
def extract_model_short_name(model_name):
    """Extract short name from model identifier.
    
    Args:
        model_name: Full model identifier (e.g., "provider/model-name")
    
    Returns:
        Short name (e.g., "model-name") or "unknown" if invalid
    """
    if not model_name:
        return "unknown"
    
    if not isinstance(model_name, str):
        return "unknown"
    
    if "/" not in model_name:
        return model_name
    
    try:
        return model_name.split("/")[-1]
    except (ValueError, IndexError):
        return "unknown"
```

### Apply to:
- `run_agent.py:2735` - Model name extraction
- `run_agent.py:4824` - JSON structure parsing
- `run_agent.py:1743` - Conversation history length

---

## Pattern 3: Fix Thread Safety Issues

### Problem
```python
_cleanup_done = False

def _run_cleanup():
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
```

**Issues:**
- Race condition: both threads see `_cleanup_done=False`
- Could run cleanup multiple times in parallel

### Solution Pattern

```python
# Pattern A: Use threading.Lock
import threading

_cleanup_lock = threading.Lock()
_cleanup_done = False

def _run_cleanup():
    global _cleanup_done
    with _cleanup_lock:
        if _cleanup_done:
            return
        _cleanup_done = True
    
    # Cleanup logic here (outside lock for performance)
    try:
        _cleanup_all_terminals()
    except Exception as e:
        logger.warning("Terminal cleanup failed: %s", e)

# Pattern B: Use threading.Event (cleaner semantics)
import threading

_cleanup_event = threading.Event()

def _run_cleanup():
    if _cleanup_event.is_set():
        return
    _cleanup_event.set()  # Atomic operation
    
    try:
        _cleanup_all_terminals()
    except Exception as e:
        logger.warning("Terminal cleanup failed: %s", e)

# Pattern C: For init code, use once-callable
from functools import lru_cache

@lru_cache(maxsize=1)
def _run_cleanup_once():
    """Cleanup runs at most once due to lru_cache."""
    try:
        _cleanup_all_terminals()
    except Exception as e:
        logger.warning("Terminal cleanup failed: %s", e)

def _run_cleanup():
    _run_cleanup_once()
```

### Apply to:
- `cli.py:510-517` - Global `_cleanup_done` flag
- `cli.py:677` - `_active_worktree` variable
- Any other global mutable state

---

## Pattern 4: Fix Asyncio Context Issues

### Problem
```python
result_json = asyncio.run(
    vision_analyze_tool(image_url=vision_source, user_prompt=analysis_prompt)
)
```

**Issues:**
- Fails in worker threads (ThreadPoolExecutor)
- Raises `RuntimeError` unpredictably

### Solution Pattern

```python
import asyncio
import threading

# Pattern A: Detect and handle thread context
async def _async_vision_analyze(image_url, user_prompt):
    from tools.vision_tools import vision_analyze_tool
    return await vision_analyze_tool(image_url=image_url, user_prompt=user_prompt)

def _call_async_safe(coro):
    """Call an async function safely from any context (main thread or worker)."""
    try:
        # Try asyncio.run() first (main thread path)
        return asyncio.run(coro)
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            # We're in a worker thread - create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        else:
            raise  # Re-raise other RuntimeErrors

# Usage
try:
    result_json = _call_async_safe(
        _async_vision_analyze(vision_source, analysis_prompt)
    )
except Exception as e:
    logger.error("Vision analysis failed: %s", e)
    description = f"Image analysis error: {e}"

# Pattern B: Run in dedicated thread pool executor (if available)
def _call_async_threaded(coro, executor=None):
    """Run async code in a thread pool."""
    import concurrent.futures
    
    executor = executor or concurrent.futures.ThreadPoolExecutor(max_workers=1)
    
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    future = executor.submit(_run)
    return future.result()
```

### Apply to:
- `run_agent.py:4821-4823` - Vision analysis call

---

## Pattern 5: Fix Duplicate Function Arguments

### Problem
```python
self.agent._persist_session(
    self.conversation_history,
    self.conversation_history,  # ← Duplicate
)
```

**Issues:**
- Session message dedup fails
- Data loss or duplication
- Intent is unclear

### Solution Pattern

```python
# Step 1: Understand the function signature
def _persist_session(self, messages: List[Dict], conversation_history: List[Dict] = None):
    """
    Args:
        messages: Current conversation messages
        conversation_history: Previous session messages (for post-compression sessions)
                              If None, defaults to len(messages) is 0
    """

# Step 2: Determine correct usage
# Case A: Normal session persistence (no prior session)
self.agent._persist_session(self.conversation_history)

# Case B: After compression (referencing previous session)
self.agent._persist_session(
    self.conversation_history,
    conversation_history=self.previous_session_messages  # Be explicit
)

# Case C: Safest - make it required to prevent mistakes
def _persist_session(self, messages: List[Dict], previous_session_length: int = 0):
    """
    Args:
        messages: Current conversation messages
        previous_session_length: Number of messages from previous session (post-compression)
    """
    # Usage: won't confuse with messages parameter
    start_idx = previous_session_length
    flush_from = max(start_idx, self._last_flushed_db_idx)
    for msg in messages[flush_from:]:
        ...
```

### Apply to:
- `cli.py:4985-4987` - Session persistence call

---

## Pattern 6: Remove Dead Code Blocks

### Problem
```python
if now - _last_countdown_refresh >= 5.0:
    _last_countdown_refresh = now
    self._invalidate()
if now - _last_countdown_refresh >= 5.0:  # ← Always False, dead code
    _last_countdown_refresh = now
    self._invalidate()
```

### Solution Pattern

```python
# Step 1: Understand original intent (check git blame)
git blame -L 5507,5512 cli.py

# Step 2: If duplicate is truly redundant, remove
if now - _last_countdown_refresh >= 5.0:
    _last_countdown_refresh = now
    self._invalidate()
# Removed duplicate

# Step 3: If there was a second different intent, fix
if now - _last_countdown_refresh >= 5.0:
    _last_countdown_refresh = now
    self._invalidate()
    
# Don't duplicate; if you need different behavior, use else:
# if now - _last_countdown_refresh >= 5.0:
#     _last_countdown_refresh = now
#     self._invalidate()
# else:
#     # Different logic here
#     pass
```

### Apply to:
- `cli.py:5507-5512` - Duplicate countdown refresh

---

## Pattern 7: Add Logging to Silent Failures

### Problem
```python
try:
    _cleanup_all_terminals()
except Exception:
    pass  # Silent failure
```

**Issues:**
- Resource leaks are invisible
- Debugging is harder
- User doesn't know what failed

### Solution Pattern

```python
import logging

logger = logging.getLogger(__name__)

# Pattern A: Info-level logging for expected failures
try:
    _cleanup_all_terminals()
except Exception as e:
    logger.info("Terminal cleanup skipped: %s", e)

# Pattern B: Warning-level for resource cleanup (should always work)
try:
    _cleanup_all_terminals()
except Exception as e:
    logger.warning("Terminal cleanup failed: %s", e)

# Pattern C: Distinguish expected vs unexpected
try:
    _cleanup_all_terminals()
except (OSError, ProcessLookupError) as e:
    # Expected: process already dead, terminal deleted, etc.
    logger.debug("Terminal cleanup skipped: %s", e)
except Exception as e:
    # Unexpected: log it for investigation
    logger.warning("Unexpected error during terminal cleanup: %s", e)
```

### Apply to:
- `cli.py:518-538` - All except blocks in `_run_cleanup()`
- Any `except Exception: pass` blocks

---

## Automated Refactoring Checklist

Use these commands to systematically find and fix issues:

```bash
# Find all broad exception handlers
grep -n "except Exception" run_agent.py cli.py hermes_state.py | wc -l

# Find all except blocks without logging
grep -A1 "except Exception" run_agent.py | grep -v "logger\|print"

# Find all asyncio.run calls
grep -n "asyncio.run(" *.py

# Find all global mutable state
grep -n "^[A-Z_]* = " cli.py | grep -v "= \""

# Find potential off-by-one errors
grep -n "\[0\]\|\[-1\]" run_agent.py | grep -v "# .*\[0\]\|\[-1\]"

# Find TODO/FIXME
grep -n "TODO\|FIXME\|XXX\|HACK" *.py
```

---

## Validation After Refactoring

```python
# Test 1: Specific exception catching
def test_json_decode_error_caught():
    with pytest.raises(ValueError):
        # Should raise ValueError, not Exception
        json.loads("invalid")
    
    # Should be caught specifically
    try:
        json.loads("invalid")
    except json.JSONDecodeError:
        pass  # Expected

# Test 2: Thread safety
def test_cleanup_not_duplicated():
    _cleanup_lock = threading.Lock()
    _cleanup_called = False
    
    def cleanup():
        nonlocal _cleanup_called
        with _cleanup_lock:
            if _cleanup_called:
                return
            _cleanup_called = True
        time.sleep(0.1)  # Simulate work
    
    # Run from multiple threads
    threads = [threading.Thread(target=cleanup) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Should only have run once (tracked by flag)
    assert _cleanup_called

# Test 3: Asyncio context handling
async def async_work():
    return "done"

def test_asyncio_in_threads():
    result_list = []
    
    def worker():
        result = asyncio_safe(async_work())
        result_list.append(result)
    
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(result_list) == 5
    assert all(r == "done" for r in result_list)
```
