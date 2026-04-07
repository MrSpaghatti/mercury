# Exception Handler Refactoring Guide

## Overview

This document outlines the systematic refactoring needed to replace ~230 broad `except Exception` handlers with specific exception types in the core agent code. This work started in Q2 2026 with the comprehensive code audit.

**Status**: In Progress (Phase 1 complete, Phase 2-3 remaining)
**Priority**: High (improves debuggability and prevents silent failures)
**Effort**: ~2-3 weeks for full refactoring

---

## Why This Matters

Broad exception handlers (`except Exception`) mask bugs and make debugging difficult:

```python
# BAD: Hides all failures including programming errors
try:
    json.loads(data)
except Exception:
    log.debug("Could not parse")
    return False

# GOOD: Catches specific expected errors, lets bugs surface
try:
    json.loads(data)
except json.JSONDecodeError:
    log.debug("Could not parse")
    return False
except (AttributeError, TypeError):
    log.error("Unexpected error structure: %s", e)
    return False
```

---

## File Statistics

| File | Total Handlers | Broad Handlers | Status |
|------|---|---|---|
| run_agent.py | 93 | 93 | Phase 2+ |
| cli.py | 133+ | 115+ | Phase 2+ |
| hermes_state.py | 4 | 2 (acceptable) | Done |
| tools/*.py | 100+ | 80+ | Phase 3 |

### Phase 1: COMPLETE ✅ 

**Fixed these critical paths:**
- Tool argument parsing (run_agent.py:284) - json.JSONDecodeError specific
- Session DB operations (run_agent.py:1772) - ValueError/TypeError distinction
- API response validation (run_agent.py:4843) - Added type checking
- Model name safety (run_agent.py:2738) - Added isinstance() check
- Thread-safe cleanup (cli.py:512-517) - Added threading.Lock()
- Subprocess validation (cli.py:4396) - Added port range validation
- Voice recording race condition (cli.py:5156) - Fixed TOCTOU bug

**Commits**: 3 (fix: Address CRITICAL/HIGH audit findings + parts 1-2)

### Phase 2: IN PROGRESS 🔄

**Recommended for next sprint:**

#### High-Traffic Paths (Focus First)
1. **API Call Error Handling** (run_agent.py:~7300+)
   - `openai.APIError`, `openai.RateLimitError`, `openai.APIConnectionError`
   - `anthropic.APIError`, `anthropic.RateLimitError`
   - Transport errors: `httpx.RemoteProtocolError`, `httpx.ReadTimeout`, `httpx.ConnectError`

2. **Tool Execution Paths** (run_agent.py:~5700+)
   - Tool callback errors: Generally OK to keep broad (callbacks should never crash agent)
   - Tool invocation errors: Distinguish between execution vs data structure errors

3. **Session Database Operations** (run_agent.py:~1000-1800)
   - Lock contention: `sqlite3.OperationalError` with "locked" or "busy" message
   - Data errors: `ValueError`, `TypeError` for invalid message structure
   - Connection errors: `sqlite3.DatabaseError`

4. **Message Processing** (run_agent.py:~1700-2000)
   - JSON parsing: Always use `json.JSONDecodeError` (never bare Exception)
   - Message format validation: Check types before operations

5. **Config Loading** (run_agent.py:~1040+)
   - Broad exceptions are OK for fallback config loading
   - Log which config failed to load for debugging

#### Acceptable to Keep Broad

These contexts should keep broad `except Exception` (document with comment):

1. **Cleanup/Finalization Paths**
   ```python
   except Exception:
       pass  # Best-effort — never fatal
   ```

2. **Callback Execution** (already has logging)
   ```python
   except Exception as e:
       log.debug(f"Callback error (non-fatal): {e}")
   ```

3. **Fallback Paths**
   ```python
   except Exception:
       use_default_value()  # Clear fallback available
   ```

### Phase 3: Tools Directory Refactoring

Tools in `tools/*.py` have ~80+ broad exception handlers. These are lower priority since tool failures are often better reported as "Tool failed: {exception}" to the user.

---

## Refactoring Patterns

### Pattern 1: JSON Parsing

```python
# Before
try:
    data = json.loads(content)
except Exception:
    return {}

# After
try:
    data = json.loads(content)
except json.JSONDecodeError:
    logging.debug("Invalid JSON: %s", content[:100])
    return {}
except (AttributeError, TypeError):
    logging.error("Unexpected data type for JSON parsing")
    return {}
```

### Pattern 2: Database Operations

```python
# Before
try:
    db.execute(query)
except Exception as e:
    logging.warning("DB failed: %s", e)

# After
try:
    db.execute(query)
except sqlite3.OperationalError as e:
    if "locked" in str(e).lower() or "busy" in str(e).lower():
        logging.debug("DB locked, retrying...")
        retry_with_backoff()
    else:
        logging.warning("DB error: %s", e)
except sqlite3.DatabaseError as e:
    logging.warning("DB corruption detected: %s", e)
except Exception as e:
    logging.warning("Unexpected DB error: %s", e)
```

### Pattern 3: External API Calls

```python
# Before
try:
    response = client.create(**kwargs)
except Exception as e:
    raise RuntimeError(f"API failed: {e}")

# After
try:
    response = client.create(**kwargs)
except anthropic.RateLimitError as e:
    logging.warning("Rate limited, will retry: %s", e)
    raise  # Caller knows how to retry
except anthropic.APIError as e:
    logging.error("API error (possible infrastructure issue): %s", e)
    raise
except httpx.ConnectError as e:
    logging.warning("Network connection failed: %s", e)
    raise
```

### Pattern 4: Callback Execution (Keep Broad)

```python
# This is OK to keep broad
if self.progress_callback:
    try:
        self.progress_callback(data)
    except Exception as e:
        logging.debug(f"Progress callback failed (non-fatal): {e}")
        # Never let callback errors crash agent
```

---

## How to Identify What Exception to Catch

1. **Check the source code or docs**
   ```bash
   # For json module
   python3 -c "import json; help(json.loads)"
   
   # For libraries, check their __init__.py or docs
   python3 -c "from anthropic import RateLimitError; print(RateLimitError.__doc__)"
   ```

2. **Run and catch the actual exception**
   ```bash
   python3 -c "import json; json.loads('invalid')" 2>&1 | head -5
   # Output: json.decoder.JSONDecodeError: ...
   ```

3. **Check imports in the file**
   ```bash
   grep "import sqlite3\|from sqlite3\|import anthropic" run_agent.py
   ```

---

## Testing Your Changes

After refactoring exception handlers, test the happy path AND error paths:

```python
# Test that specific exception is caught
try:
    json.loads("{invalid json}")
    assert False, "Should have raised"
except json.JSONDecodeError:
    pass  # Expected

# Test that other exceptions are NOT caught (for specific handlers)
try:
    json.loads("{valid json}")
    json_data.missing_key.nested  # This raises AttributeError
except json.JSONDecodeError:
    assert False, "Should not catch AttributeError"
```

---

## Rollout Strategy

1. **Week 1**: Fix high-traffic critical paths (API calls, tool execution)
2. **Week 2**: Fix remaining core agent paths (message processing, DB ops)
3. **Week 3**: Tools directory refactoring
4. **After**: Enable pylint rule to prevent regressions

---

## Exceptions That Are Already Specific ✅

The following areas already have specific exception handling (review for patterns):

- Message format validation (line 1749+)
- Tool call parsing (line 284) - Recently fixed
- Session DB append (line 1772) - Recently fixed
- API stream error handling (line 3786+)
- Trajectory conversion (line 1902+)

---

## Questions or Issues?

- Check AUDIT_REPORT.md section "Category 4: Broad Exception Handling" for full issue details
- See AUDIT_FINDINGS_CRITICAL.md for high-priority critical issues that were fixed first
- Reference AUDIT_REFACTORING_PATTERNS.md for before/after code examples

---

## Future: Automated Checks

Once refactoring is complete, enable these linting rules:

```toml
# pyproject.toml
[tool.pylint.messages_control]
enable = ["broad-exception-caught"]  # Warn on bare "except Exception"

# .flake8
extend-ignore = []
select = E,W,F,C
max-line-length = 120
```

This will prevent new broad exception handlers from being added.
