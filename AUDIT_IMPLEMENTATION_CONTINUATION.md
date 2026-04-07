# Audit Implementation Continuation - Session Handoff

## What Was Completed (Q2 2026, Session 1)

A comprehensive code audit identified 29 issues across the Hermes Agent codebase. **Phase 1 of fixes is complete:**

### Critical Issues ✅ FIXED
1. **Session Message Duplication** (cli.py:4985-4987)
   - Problem: Duplicate `conversation_history` parameter causing incorrect session flush logic
   - Fix: Removed second parameter, relying on default None behavior
   - Commit: 6247578a

2. **asyncio.run() Thread Safety** (run_agent.py:4821-4823)
   - Problem: Called from worker threads, causing RuntimeError
   - Fix: Added fallback to create new event loop when needed
   - Commit: 6247578a

### High Issues ✅ FIXED
1. **Duplicate Dead Code Block** (cli.py:5507-5512)
   - Fix: Removed unreachable duplicate countdown refresh code
   - Commit: 6247578a

2. **Broad Exception Handlers - Phase 1** (Multiple files)
   - Fixed critical paths with specific exception types
   - Created comprehensive refactoring guide
   - Commits: 7e083215, 882edd25, 4789d370

### Medium Issues ✅ FIXED
- API response validation (type checking)
- Model name safety (isinstance check)
- Thread-safe cleanup (threading.Lock)
- Voice recording race condition (TOCTOU fix)
- Subprocess port validation
- Cleanup logging

## What Remains: Phase 2-3 Exception Handler Refactoring

**Status:** ~230 broad `except Exception` handlers remain across the codebase

### Reference Documents Created
1. **EXCEPTION_HANDLER_REFACTORING.md** - Complete refactoring guide
2. **AUDIT_REPORT.md** - Full 500+ line audit with all 29 issues
3. **AUDIT_FINDINGS_CRITICAL.md** - Critical issues with detailed fixes

### Phase 2: High-Traffic Paths (Recommended Priority)

**Effort:** ~1 week
**Focus on these files:** run_agent.py (main API paths), cli.py (UI/cleanup paths)

#### 1. API Call Error Handling (run_agent.py ~7300+)
**Current:** Line 7318 catches `except Exception as api_error`
**Expected:** Distinguish between:
- `openai.APIError`, `openai.RateLimitError`, `openai.APIConnectionError`
- `anthropic.APIError`, `anthropic.RateLimitError`  
- `httpx.RemoteProtocolError`, `httpx.ReadTimeout`, `httpx.ConnectError`
- `UnicodeEncodeError` (already handled, line 7333)
- Transport/connection errors

**Test:** Make sure rate limit errors trigger retry logic, not abort

#### 2. Tool Execution Paths (run_agent.py ~5700-5800)
**Current:** Tool callbacks catch broad exceptions (mostly OK)
**Action:** Keep broad but add comment explaining why (callbacks must not crash agent)
**Note:** Tool invocation errors (line 5785) should distinguish execution failures from data errors

#### 3. Session Database Operations (run_agent.py ~1000-1800)
**Status:** Partially fixed
**Remaining:** Add specific handlers for different lock contention scenarios
**Pattern:**
```python
except sqlite3.OperationalError as e:
    if "locked" in str(e).lower():
        # Handle lock contention with retry
    else:
        # Handle other operational errors
```

#### 4. Message Processing & JSON (run_agent.py ~1700-2000)
**Current:** Multiple try/except blocks with broad handlers
**Action:** Replace with `json.JSONDecodeError` for parsing, type checks before operations

#### 5. Config Loading (run_agent.py ~1040-1150)
**Current:** Broad exceptions for fallback config (acceptable)
**Action:** Add logging to identify which config failed (helps debugging)
**Example:** Line 1150 - add debug log for skills config failure

### Phase 3: Tools Directory Refactoring

**Effort:** ~1 week
**Files:** tools/*.py (80+ broad exception handlers)
**Priority:** Lower - tool failures are generally reported to user

**Strategy:**
- Focus on tools that handle external APIs (file operations, network calls)
- Keep broad exceptions in internal/helper tools
- Always log the actual exception for debugging

### Checklist for Phase 2 Work

- [ ] Identify top 5 API error paths (use code coverage to find hot paths)
- [ ] Create specific exception handlers for openai/anthropic/httpx errors
- [ ] Add logging to distinguish between error types
- [ ] Test each path:
  - [ ] Rate limit scenario (should trigger retry)
  - [ ] Connection timeout (should retry or fail gracefully)
  - [ ] Invalid API response (should log and handle)
  - [ ] Malformed JSON in response (should handle gracefully)
- [ ] Update EXCEPTION_HANDLER_REFACTORING.md with completed sections
- [ ] Commit with clear message referencing audit issue #4.1

## How to Continue

### Step 1: Pick a Path
Start with one of the high-traffic paths above (e.g., "API Call Error Handling").

### Step 2: Understand the Current Exception Types
```bash
# Find all exception types caught in that path
grep -n "except Exception" run_agent.py | awk -F: '{print $1}' | sed 's/^//' | xargs -I {} sed -n '{}p;$(({}+50))p' run_agent.py | head -100
```

### Step 3: Identify What Should Be Caught
Check the libraries being used:
```bash
# What exceptions can Anthropic SDK raise?
python3 -c "from anthropic import APIError, RateLimitError; print('Available')"

# What exceptions from httpx?
python3 -c "import httpx; print(dir(httpx))" | grep -i error
```

### Step 4: Refactor One Exception Handler
Follow the patterns in EXCEPTION_HANDLER_REFACTORING.md, section "Refactoring Patterns".

### Step 5: Test and Commit
```bash
# Verify syntax
python3 -m py_compile run_agent.py

# Commit with reference to audit issue
git commit -m "fix: Refactor API error handling (audit #4.1 part 1)

Specific changes:
- Catch anthropic.RateLimitError specifically to trigger retry
- Catch httpx.ConnectError for network failures
- Catch anthropic.APIError for infrastructure issues
- Keep generic Exception as fallback with detailed logging

Remaining: X handlers in Y files"
```

## Key Files to Reference

1. **EXCEPTION_HANDLER_REFACTORING.md** - Complete guide with patterns
2. **AUDIT_REPORT.md** - Full details of all 29 issues
3. **run_agent.py** - ~7,950 lines, ~93 broad exception handlers
4. **cli.py** - ~7,962 lines, ~115+ broad exception handlers

## Current Exception Handler Counts

| File | Total | Broad | Status |
|------|-------|-------|--------|
| run_agent.py | 93 | 93 | Phase 2+ |
| cli.py | 133+ | 115+ | Phase 2+ |
| hermes_state.py | 4 | 2 | ✅ OK (config fallbacks) |
| tools/*.py | 100+ | 80+ | Phase 3 |

## Estimated Effort

- **Phase 2 (High-Traffic):** 1 week (5 main paths × ~1 day each)
- **Phase 3 (Tools):** 1 week (systematic refactoring)
- **Testing & CI Setup:** 2-3 days

**Total:** 2-3 weeks for full completion

## Success Criteria

✅ All critical paths have specific exception handlers
✅ Logging distinguishes between expected and unexpected failures
✅ No silent failures in critical paths (cleanup, persistence, API calls)
✅ Easy to debug in production (clear exception messages)
✅ Can enable pylint rule `broad-exception-caught` to prevent regressions

## After Phase 2 Complete

Enable automated checks to prevent regressions:

```toml
# pyproject.toml
[tool.pylint.messages_control]
enable = ["broad-exception-caught"]  # Warn on bare "except Exception"
```

This will catch any NEW broad exception handlers added in future PRs.

---

**Created:** 2026-04-06  
**Last Updated:** 2026-04-06  
**Next Session Target:** Begin Phase 2 API error handling refactoring
