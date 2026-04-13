#!/usr/bin/env python3
"""Heuristic Sanitizer — Post-mortem error analysis from audit logs.

Reads the audit log, identifies failed Level 3+ actions, cross-references
with live environment state, and generates a Correction Report with actionable
fix suggestions.

Registered as: heuristic_sanitize (toolname)
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Risk threshold — only analyze actions at or above this level
MIN_RISK_LEVEL = 3


# ---------------------------------------------------------------------------
# Environment introspection helpers
# ---------------------------------------------------------------------------

def _run_check(cmd: List[str], timeout: int = 10) -> Tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as exc:
        return -1, "", str(exc)


def _get_env_state() -> dict:
    """Snapshot current environment for cross-referencing."""
    state: dict = {}

    # Python packages
    rc, out, _ = _run_check(["pip", "list", "--format=json"])
    if rc == 0 and out:
        try:
            state["python_packages"] = {
                p.get("name", p.get("Name", "")).lower()
                for p in json.loads(out)
            }
        except (json.JSONDecodeError, KeyError):
            state["python_packages"] = set()
    else:
        state["python_packages"] = set()

    # System PATH
    state["path_dirs"] = os.environ.get("PATH", "").split(os.pathsep)

    # Available binaries
    bin_names = set()
    for d in state["path_dirs"]:
        if os.path.isdir(d):
            try:
                bin_names.update(os.listdir(d))
            except OSError:
                pass
    state["binaries"] = bin_names

    # OS info
    rc, out, _ = _run_check(["uname", "-a"])
    state["os_info"] = out if rc == 0 else "unknown"

    # Shell
    state["shell"] = os.environ.get("SHELL", "unknown")

    # Virtual env
    state["virtualenv"] = bool(
        os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_DEFAULT_ENV")
    )

    return state


# ---------------------------------------------------------------------------
# Heuristic rules — pattern matching for common failure modes
# ---------------------------------------------------------------------------

HEURISTIC_RULES: List[dict] = [
    # --- Command not found ---
    {
        "name": "missing_command",
        "patterns": [
            r"command not found",
            r"'[^']+' is not recognized",
            r"executable not found",
            r"no such file or directory",
        ],
        "description": "Command/CLI tool not found on PATH",
        "fix_template": (
            "The command '{command}' is not available. Fix:\n"
            "  1. Install: pip install {package}  (or apt/brew/yum)\n"
            "  2. Verify: which {command}\n"
            "  3. Add to PATH if installed in non-standard location"
        ),
        "env_check": "check if '{command}' is in installed binaries",
    },
    # --- Permission denied ---
    {
        "name": "permission_denied",
        "patterns": [
            r"[Pp]ermission denied",
            r"[Ff]orbidden",
            r"[Ee]rrno 13",
            r"[Ee]rrno 1",
        ],
        "description": "Insufficient permissions",
        "fix_template": (
            "Permission denied for '{command}'. Fix:\n"
            "  1. Check file/directory ownership: ls -la {path}\n"
            "  2. Use sudo if system-level: sudo {command}\n"
            "  3. Fix ownership: sudo chown $USER {path}"
        ),
        "env_check": "check current user and target file ownership",
    },
    # --- Module/package missing ---
    {
        "name": "missing_module",
        "patterns": [
            r"ModuleNotFoundError: No module named '([^']+)'",
            r"ImportError: cannot import name",
            r"ModuleNotFoundError",
        ],
        "description": "Python module not installed",
        "fix_template": (
            "Python module '{module}' is not installed. Fix:\n"
            "  1. Install: pip install {module}\n"
            "  2. If in virtualenv, ensure it is activated\n"
            "  3. Check requirements.txt: pip install -r requirements.txt"
        ),
        "env_check": "cross-reference '{module}' against pip list",
    },
    # --- Connection/network ---
    {
        "name": "network_error",
        "patterns": [
            r"Connection refused",
            r"timeout",
            r"ETIMEDOUT",
            r"Network is unreachable",
            r"getaddrinfo failed",
        ],
        "description": "Network connectivity issue",
        "fix_template": (
            "Network error accessing '{command}'. Fix:\n"
            "  1. Check connectivity: ping -c 1 {host}\n"
            "  2. Check DNS: nslookup {host}\n"
            "  3. Verify proxy settings if behind corporate firewall"
        ),
        "env_check": "check network connectivity and DNS resolution",
    },
    # --- Disk space ---
    {
        "name": "disk_space",
        "patterns": [
            r"No space left on device",
            r"ENOSPC",
            r"[Ee]rrno 28",
        ],
        "description": "Insufficient disk space",
        "fix_template": (
            "Disk space exhausted. Fix:\n"
            "  1. Check usage: df -h\n"
            "  2. Find large files: du -sh /* | sort -rh | head -10\n"
            "  3. Clean: docker system prune, apt clean, or remove old logs"
        ),
        "env_check": "check disk usage with df -h",
    },
    # --- Git errors ---
    {
        "name": "git_error",
        "patterns": [
            r"git.*fatal:",
            r"git.*error:",
            r"CONFLICT.*contents",
            r"rejected.*remote",
            r".*up to date.*force",
        ],
        "description": "Git operation failed",
        "fix_template": (
            "Git operation failed for: '{command}'. Fix:\n"
            "  1. Check status: git status\n"
            "  2. Fetch updates: git fetch origin\n"
            "  3. Resolve conflicts or rebase if needed"
        ),
        "env_check": "check git repo state",
    },
    # --- Generic fallback ---
    {
        "name": "generic_failure",
        "patterns": [
            r"[Ee]rrno",
            r"[Ee]xception",
            r"[Ff]ailed",
            r"[Ee]rror",
            r"[Tt]raceback",
        ],
        "description": "General failure",
        "fix_template": (
            "Command failed: '{command}'\n"
            "  Error: {error_snippet}\n"
            "  Review the error output and adjust the command accordingly."
        ),
        "env_check": "manual review required",
    },
]


def _match_heuristic(error_msg: str, command: str) -> Optional[dict]:
    """Match an error message to the most specific heuristic rule."""
    for rule in HEURISTIC_RULES:
        for pattern in rule["patterns"]:
            m = re.search(pattern, error_msg, re.IGNORECASE)
            if m:
                return {
                    "rule": rule["name"],
                    "description": rule["description"],
                    "matched_pattern": pattern,
                    "match_group": m.group(1) if m.lastindex else None,
                }
    return None


def _suggest_package_for_command(command: str, env_state: dict) -> str:
    """Guess the install package name for a command."""
    cmd_base = command.split()[0] if command else "unknown"

    # Common mappings
    known_packages = {
        "docker": "docker", "kubectl": "kubectl", "aws": "awscli",
        "jq": "jq", "curl": "curl", "wget": "wget", "git": "git",
        "node": "nodejs", "npm": "npm", "yarn": "yarn",
        "cargo": "rustc", "rustc": "rustc",
        "pip": "pip", "pip3": "pip3",
    }
    return known_packages.get(cmd_base, cmd_base)


def _suggest_package_for_module(module_name: str) -> str:
    """Map a Python module name to its pip package name."""
    known = {
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "PIL": "Pillow",
        "yaml": "PyYAML",
        "bs4": "beautifulsoup4",
        "dotenv": "python-dotenv",
    }
    return known.get(module_name, module_name)


# ---------------------------------------------------------------------------
# Audit log reader (reuses action_auditor's get_audit_summary where possible)
# ---------------------------------------------------------------------------

def _read_audit_log() -> List[dict]:
    """Read all entries from the audit log."""
    try:
        from hermes_constants import get_hermes_home
        hermes_home = get_hermes_home()
    except Exception:
        hermes_home = os.path.expanduser("~/.hermes")

    log_path = Path(hermes_home) / "logs" / "audit.log.jsonl"
    if not log_path.exists():
        return []

    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _find_failed_high_risk(entries: List[dict]) -> List[dict]:
    """Filter for failed actions at risk level >= MIN_RISK_LEVEL."""
    failed = []
    seen_tools = set()  # dedup by tool+action in recent window

    for entry in entries:
        risk = entry.get("risk_level", 0)
        status = entry.get("status", "")

        if risk >= MIN_RISK_LEVEL and status == "failed":
            key = (entry.get("tool"), entry.get("action", "")[:100])
            if key not in seen_tools:
                seen_tools.add(key)
                failed.append(entry)

    return failed


# ---------------------------------------------------------------------------
# Correction Report generator
# ---------------------------------------------------------------------------

def generate_correction_report(
    failed_entries: List[dict], env_state: dict
) -> str:
    """Generate a human-readable Correction Report."""
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("HEURISTIC SANITIZER — Correction Report")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Analyzing {len(failed_entries)} failed high-risk action(s)")
    lines.append("=" * 60)
    lines.append("")

    if not failed_entries:
        lines.append("No failed high-risk actions found in audit log.")
        lines.append("Environment is healthy.")
        return "\n".join(lines)

    for idx, entry in enumerate(failed_entries, 1):
        tool = entry.get("tool", "unknown")
        action = entry.get("action", "unknown")
        risk = entry.get("risk_level", "?")
        ts = entry.get("timestamp", "?")
        duration = entry.get("duration_ms")
        error = entry.get("error", "")

        lines.append(f"[{idx}] Failed Action (Risk Level {risk})")
        lines.append(f"    Timestamp: {ts}")
        lines.append(f"    Tool:      {tool}")
        lines.append(f"    Command:   {action[:120]}")
        if duration:
            lines.append(f"    Duration:  {duration}ms")
        if error:
            lines.append(f"    Error:     {error[:200]}")
        lines.append("")

        # Heuristic matching
        match = _match_heuristic(error or "", action or "")
        if match:
            lines.append(f"    Diagnosis: {match['description']}")
            lines.append(f"    Rule:      {match['rule']}")
            lines.append("")

            # Build fix suggestion
            cmd_base = action.split()[0] if action else "unknown"
            module = match.get("match_group") or "unknown"

            if match["rule"] == "missing_command":
                pkg = _suggest_package_for_command(cmd_base, env_state)
                binaries = env_state.get("binaries", set())
                available = "yes" if cmd_base in binaries else "not found on PATH"
                fix = match["rule_obj"].get("fix_template", "") if "rule_obj" in match else ""
                lines.append(f"    Environment check: '{cmd_base}' in PATH = {available}")
                lines.append(f"    Suggested fix: pip install {pkg} (or apt/brew)")
                lines.append("")

            elif match["rule"] == "missing_module":
                pkg = _suggest_package_for_module(module)
                installed = env_state.get("python_packages", set())
                available = "yes" if module.lower() in installed else "not installed"
                lines.append(f"    Environment check: '{module}' in pip list = {available}")
                lines.append(f"    Suggested fix: pip install {pkg}")
                lines.append("")

            else:
                # Generic fix template
                fix = HEURISTIC_RULES[
                    next(i for i, r in enumerate(HEURISTIC_RULES)
                         if r["name"] == match["rule"])
                ]["fix_template"]
                fix_filled = fix.format(
                    command=cmd_base,
                    package=_suggest_package_for_command(cmd_base, env_state),
                    module=_suggest_package_for_module(module),
                    error_snippet=error[:100] if error else "N/A",
                    path=action.split()[-1] if action else ".",
                    host=cmd_base,
                )
                lines.append(f"    Environment check: {HEURISTIC_RULES[0].get('env_check', 'manual')}")
                for fix_line in fix_filled.split("\n"):
                    lines.append(f"    {fix_line}")
                lines.append("")

            # Preventive config suggestion
            lines.append(f"    Preventive action:")
            if match["rule"] == "missing_command":
                lines.append(f"      Add 'apt install {cmd_base}' to setup/bootstrap script")
            elif match["rule"] == "missing_module":
                pkg = _suggest_package_for_module(module)
                lines.append(f"      Add '{pkg}' to requirements.txt")
            elif match["rule"] == "permission_denied":
                lines.append(f"      Run agent with appropriate user permissions")
        else:
            lines.append(f"    No specific heuristic match — manual review recommended")
            lines.append("")

        lines.append("-" * 60)
        lines.append("")

    # Summary
    lines.append("SUMMARY")
    tool_counts: Dict[str, int] = {}
    for entry in failed_entries:
        t = entry.get("tool", "unknown")
        tool_counts[t] = tool_counts.get(t, 0) + 1
    for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {tool}: {count} failure(s)")
    lines.append("")

    # Environment snapshot
    lines.append("ENVIRONMENT SNAPSHOT")
    lines.append(f"  OS:         {env_state.get('os_info', 'unknown')[:80]}")
    lines.append(f"  Shell:      {env_state.get('shell', 'unknown')}")
    lines.append(f"  Virtualenv: {env_state.get('virtualenv', False)}")
    pkgs = env_state.get("python_packages", set())
    lines.append(f"  Packages:   {len(pkgs)} installed")
    path_dirs = env_state.get("path_dirs", [])
    lines.append(f"  PATH:       {len(path_dirs)} directories")
    lines.append("")
    lines.append("=" * 60)
    lines.append("End of Correction Report")
    lines.append("=" * 60)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main tool handler
# ---------------------------------------------------------------------------

def heuristic_sanitize_task(args: dict, **kwargs) -> str:
    """
    Analyze audit log for failed high-risk actions and generate a Correction Report.

    Reads ~/.hermes/logs/audit.log.jsonl, finds failed actions at risk
    level >= 3, cross-references with live environment state (pip list, PATH,
    available binaries), and returns a structured report with fix suggestions.
    """
    risk_threshold = args.get("min_risk_level", MIN_RISK_LEVEL)
    limit = args.get("limit", 20)

    # Read audit log
    entries = _read_audit_log()
    if not entries:
        return json.dumps({
            "status": "ok",
            "report": "No audit log entries found. The Action Auditor may not be active yet.",
            "entries_analyzed": 0,
            "failures_found": 0,
        })

    # Filter failures at or above risk threshold
    failed = _find_failed_high_risk(entries)
    failed = [e for e in failed if e.get("risk_level", 0) >= risk_threshold]
    failed = failed[:limit]

    if not failed:
        return json.dumps({
            "status": "ok",
            "report": "No failed high-risk actions found in audit log. Environment is healthy.",
            "entries_analyzed": len(entries),
            "failures_found": 0,
        })

    # Snapshot environment
    env_state = _get_env_state()

    # Generate report
    report = generate_correction_report(failed, env_state)

    return json.dumps({
        "status": "ok",
        "report": report,
        "entries_analyzed": len(entries),
        "failures_found": len(failed),
    })


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def check_requirements() -> bool:
    """Check that the audit log path is accessible."""
    try:
        from hermes_constants import get_hermes_home
        hermes_home = get_hermes_home()
    except Exception:
        hermes_home = os.path.expanduser("~/.hermes")
    log_dir = Path(hermes_home) / "logs"
    return log_dir.is_dir() or Path(hermes_home).is_dir()


from tools.registry import registry

registry.register(
    name="heuristic_sanitize",
    toolset="audit",
    schema={
        "name": "heuristic_sanitize",
        "description": (
            "Analyze the audit log for failed high-risk actions and generate a "
            "Correction Report. Reads audit.log.jsonl, finds failed actions at "
            "risk level >= 3, cross-references with live environment state "
            "(pip list, PATH, binaries), and returns fix suggestions. "
            "Use after encountering errors to get automated remediation advice."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min_risk_level": {
                    "type": "integer",
                    "description": "Minimum risk level to analyze (1–5, default: 3)",
                    "default": 3,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of failures to include in report",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    handler=lambda args, **kw: heuristic_sanitize_task(args, **kw),
    check_fn=check_requirements,
    requires_env=[],
    description="Analyze audit log for failed high-risk actions, cross-reference with environment, generate Correction Report",
    emoji="🔬",
)
