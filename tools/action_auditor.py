#!/usr/bin/env python3
"""Action Auditor — Structured audit logging for every shell command and file modification.

Logs all tool invocations with timestamps, intended outcomes, and risk levels (1-5).
Hooks into Hermes's plugin system via pre_tool_call / post_tool_call.

Log Format (JSONL):
    {"timestamp": "2025-01-15T14:32:00.000000", "tool": "terminal",
     "action": "git push", "risk_level": 4, "status": "completed",
     "task_id": "xyz", "duration_ms": 230}

Audit Log Location: ~/.hermes/logs/audit.log.jsonl
"""

import json
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUDIT_LOG_NAME = "audit.log.jsonl"
_DEFAULT_HERMES_HOME = os.path.expanduser("~/.hermes")

# Risk classification mapping: tool_name -> default risk level
TOOL_RISK_LEVELS = {
    # Level 5 — Destructive, irreversible
    "terminal": 5,
    # Level 4 — File mutations, data changes
    "write_file": 4,
    "patch": 4,
    # Level 3 — State changes, process management
    "browser_navigate": 3,
    "browser_click": 3,
    "browser_type": 3,
    "process": 3,
    "cronjob": 3,
    "delegate_task": 3,
    # Level 2 — Read operations with side effects (caching)
    "browser_snapshot": 2,
    "browser_get_images": 2,
    "search_files": 2,
    "web_search": 2,
    "web_extract": 2,
    # Level 1 — Read-only, no side effects
    "read_file": 1,
    "vision_analyze": 1,
    "text_to_speech": 1,
}

# Actions that escalate terminal commands beyond default risk
_RISK_ESCALATIONS = {
    # Patterns that push terminal commands to level 5 regardless
    5: ["rm -rf", "mkfs", "dd if=", "chmod 777", "sudo rm", "> /dev/",
        "DROP TABLE", "DELETE FROM", "TRUNCATE", ":(){ :|:& };:"],
    # Patterns that push to level 4
    4: ["git push", "git force", "scp ", "rsync ", "docker rm",
        "kubectl delete", "DROP DATABASE", "ALTER TABLE",
        "apt remove", "yum remove", "dnf remove",
        "pip uninstall"],
    # Patterns that push to level 3
    3: ["git commit", "git merge", "git rebase", "docker build",
        "systemctl", "make install", "npm install", "pip install",
        "CREATE TABLE", "INSERT INTO", "UPDATE SET"],
}


def get_hermes_home() -> str:
    """Resolve Hermes home directory, falling back to default."""
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home()
    except Exception:
        return os.environ.get("HERMES_HOME", _DEFAULT_HERMES_HOME)


def _get_audit_log_path() -> Path:
    """Get the audit log file path."""
    return Path(get_hermes_home()) / "logs" / AUDIT_LOG_NAME


def _get_risk_level(tool_name: str, args: dict) -> int:
    """Determine risk level (1-5) for a tool invocation."""
    base_risk = TOOL_RISK_LEVELS.get(tool_name, 2)

    # For terminal commands, inspect the command string
    if tool_name == "terminal":
        command = args.get("command", "") if isinstance(args, dict) else ""
        for level, patterns in sorted(_RISK_ESCALATIONS.items(), reverse=True):
            if any(p in command.lower() for p in patterns):
                return max(base_risk, level)

    return base_risk


def _extract_action_summary(tool_name: str, args: dict) -> str:
    """Extract a human-readable action summary from tool arguments."""
    if not isinstance(args, dict):
        return str(args)[:200]

    if tool_name == "terminal":
        cmd = args.get("command", "")
        # Truncate long commands
        if len(cmd) > 300:
            return cmd[:300] + "..."
        return cmd

    if tool_name in ("write_file",):
        path = args.get("path", "unknown")
        return f"Write file: {path}"

    if tool_name == "patch":
        path = args.get("path", "unknown")
        old = args.get("old_string", "")[:80]
        return f"Patch {path}: '{old}' -> ..."

    if tool_name == "read_file":
        return f"Read: {args.get('path', 'unknown')}"

    if tool_name == "search_files":
        return f"Search: pattern='{args.get('pattern', '')}'"

    # Generic: first few meaningful args
    summary_parts = []
    for key, val in args.items():
        if key not in ("tool_call_id", "session_id", "task_id", "user_task"):
            v_str = str(val)[:100]
            summary_parts.append(f"{key}={v_str}")
            if len(summary_parts) >= 3:
                break
    return ", ".join(summary_parts)


# ---------------------------------------------------------------------------
# Session state for timing
# ---------------------------------------------------------------------------

_active_calls: dict = {}  # key: (tool_name, task_id, tool_call_id) -> start_time
_lock = threading.Lock()


def audit_pre(tool_name: str, args: dict, task_id: str,
              tool_call_id: str, session_id: str) -> None:
    """Called before a tool executes. Logs the action intent."""
    ts = datetime.now(timezone.utc).isoformat()
    risk = _get_risk_level(tool_name, args)
    action = _extract_action_summary(tool_name, args)

    entry = {
        "timestamp": ts,
        "tool": tool_name,
        "action": action,
        "risk_level": risk,
        "status": "started",
        "task_id": task_id,
        "session_id": session_id,
        "tool_call_id": tool_call_id,
    }

    # Track start time for the post call
    call_key = (tool_name, task_id, tool_call_id)
    with _lock:
        _active_calls[call_key] = time.monotonic()

    _write_log(entry)


def audit_post(tool_name: str, args: dict, result: str, task_id: str,
               tool_call_id: str, session_id: str) -> None:
    """Called after a tool executes. Logs completion/failure and duration."""
    ts = datetime.now(timezone.utc).isoformat()

    # Calculate duration
    call_key = (tool_name, task_id, tool_call_id)
    duration_ms = None
    with _lock:
        start = _active_calls.pop(call_key, None)
    if start is not None:
        duration_ms = round((time.monotonic() - start) * 1000, 1)

    # Determine status from result
    status = "completed"
    error = None
    try:
        result_data = json.loads(result) if isinstance(result, str) else result
        if isinstance(result_data, dict) and "error" in result_data:
            status = "failed"
            error = str(result_data["error"])[:500]
    except (json.JSONDecodeError, TypeError):
        pass

    entry = {
        "timestamp": ts,
        "tool": tool_name,
        "action": _extract_action_summary(tool_name, args),
        "risk_level": _get_risk_level(tool_name, args),
        "status": status,
        "task_id": task_id,
        "session_id": session_id,
        "tool_call_id": tool_call_id,
        "duration_ms": duration_ms,
    }
    if error:
        entry["error"] = error

    _write_log(entry)


def _write_log(entry: dict) -> None:
    """Write a single audit entry to the JSONL log file."""
    try:
        log_path = _get_audit_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Never let logging failures break tool execution
        import logging
        logging.getLogger(__name__).warning(
            "Audit log write failed: %s", e
        )


# ---------------------------------------------------------------------------
# Query utilities
# ---------------------------------------------------------------------------

def get_audit_summary(limit: int = 50, tool: str = None,
                      risk_min: int = None) -> list:
    """Read recent audit entries with optional filtering."""
    log_path = _get_audit_log_path()
    if not log_path.exists():
        return []

    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if tool and entry.get("tool") != tool:
                continue
            if risk_min and entry.get("risk_level", 0) < risk_min:
                continue
            entries.append(entry)

    return entries[-limit:]


def get_risk_distribution() -> dict:
    """Return a summary of risk level distribution from the audit log."""
    log_path = _get_audit_log_path()
    if not log_path.exists():
        return {}

    dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                rl = entry.get("risk_level", 0)
                if rl in dist:
                    dist[rl] += 1
            except (json.JSONDecodeError, ValueError):
                continue

    return dist


# ---------------------------------------------------------------------------
# Plugin Hook Registration
# ---------------------------------------------------------------------------

def init_plugin(hooks):
    """Register audit hooks with the Hermes plugin system."""
    hooks.register("pre_tool_call", _plugin_pre)
    hooks.register("post_tool_call", _plugin_post)


def _plugin_pre(tool_name, args, task_id, session_id, tool_call_id, **kwargs):
    """Pre-tool-call hook handler."""
    try:
        audit_pre(tool_name, args or {}, task_id or "",
                  tool_call_id or "", session_id or "")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Audit pre-hook error: %s", e)


def _plugin_post(tool_name, args, result, task_id, session_id,
                 tool_call_id, **kwargs):
    """Post-tool-call hook handler."""
    try:
        audit_post(tool_name, args or {}, result or "", task_id or "",
                   tool_call_id or "", session_id or "")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Audit post-hook error: %s", e)
