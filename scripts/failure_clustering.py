#!/usr/bin/env python3
"""
Weekly failure clustering analysis.

Analyzes audit_log for failure patterns in the last 7 days and:
1. Groups failures by (intent_category, failure_reason)
2. Generates eval case stubs for novel patterns (count >= 3)
3. Outputs human-readable report to logs/failure_clusters_YYYY-MM-DD.md
4. Outputs structured JSON to logs/failure_clusters_YYYY-MM-DD.json

Handles empty audit_log gracefully (insufficient data case).
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class FailureClusteringAnalyzer:
    """Analyzes audit_log for failure patterns."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize analyzer with path to state.db."""
        self.db_path = db_path or Path.home() / ".hermes" / "state.db"
        self.findings = {
            "timestamp": datetime.now().isoformat(),
            "analysis_window_days": 7,
            "total_audit_entries": 0,
            "failure_entries_count": 0,
            "failure_patterns": [],
            "generated_eval_stubs": [],
            "status": "success",
            "message": ""
        }

    def query_failure_patterns(self) -> List[Tuple[str, str, int, int]]:
        """
        Query audit_log for failure patterns in last 7 days.

        Returns:
            List of (intent_category, failure_reason, count, distinct_sessions)
        """
        patterns = []

        if not self.db_path.exists():
            logger.warning(f"Database not found at {self.db_path}")
            self.findings["status"] = "insufficient_data"
            self.findings["message"] = "Database not found"
            return patterns

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                # Get total audit entries for context
                cursor = conn.execute("SELECT COUNT(*) as count FROM audit_log")
                self.findings["total_audit_entries"] = cursor.fetchone()["count"]

                # Query failures in last 7 days
                # Note: using strftime with '%s' for Unix timestamp
                # failure_reason IS NOT NULL filters for actual failures
                cursor = conn.execute("""
                    SELECT
                        intent_category,
                        failure_reason,
                        COUNT(*) as count,
                        COUNT(DISTINCT session_id) as sessions
                    FROM audit_log
                    WHERE failure_reason IS NOT NULL
                      AND timestamp > (strftime('%s', 'now') - 7 * 86400)
                    GROUP BY intent_category, failure_reason
                    ORDER BY count DESC
                    LIMIT 10
                """)

                rows = cursor.fetchall()
                self.findings["failure_entries_count"] = sum(row["count"] for row in rows)

                for row in rows:
                    patterns.append((
                        row["intent_category"],
                        row["failure_reason"],
                        row["count"],
                        row["sessions"]
                    ))

        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                logger.info("audit_log table does not exist yet")
                self.findings["status"] = "insufficient_data"
                self.findings["message"] = "audit_log table not found"
            else:
                logger.error(f"Database error: {e}")
                self.findings["status"] = "error"
                self.findings["message"] = str(e)
        except Exception as e:
            logger.error(f"Error querying failure patterns: {e}")
            self.findings["status"] = "error"
            self.findings["message"] = str(e)

        return patterns

    def generate_eval_stub(
        self,
        intent_category: str,
        failure_reason: str,
        count: int,
        sessions: int
    ) -> str:
        """
        Generate a test stub for a failure pattern.

        Returns:
            Python test function as string
        """
        test_name = f"test_{intent_category}_{failure_reason}"
        test_name = test_name.lower().replace(" ", "_").replace("-", "_")

        # Sanitize for valid Python identifier
        test_name = "".join(c if c.isalnum() or c == "_" else "_" for c in test_name)

        stub = f'''"""
AUTO-GENERATED - Review before promoting to canonical

Failure Pattern: {intent_category} / {failure_reason}
Occurrences: {count} in last 7 days ({sessions} sessions)
Generated: {self.findings['timestamp']}

This test case was automatically generated from observed failures.
Review the pattern and adjust assertions as needed before adding to canonicals.
"""


def {test_name}():
    """
    Canonical case: Verify agent handles {intent_category}/{failure_reason} pattern.

    This case was generated from {count} observed failures in the audit_log.

    TODO: Implement setup and assertions based on failure pattern.

    Returns:
        float: Score 0.0-1.0 (1.0 = success, 0.0 = failure)
    """
    # TODO: Replace with actual test logic
    # Example structure:
    # agent_response = {{
    #     "tools_called": [...],
    #     "result": "...",
    #     ...
    # }}
    #
    # if <success_condition>:
    #     return 1.0
    # else:
    #     return 0.0

    return 0.5  # Placeholder: unimplemented test


if __name__ == "__main__":
    score = {test_name}()
    print(f"{test_name}: {{score}}")
'''

        return stub

    def generate_eval_stubs(self, patterns: List[Tuple[str, str, int, int]]) -> None:
        """Generate eval case stubs for patterns with count >= 3."""
        generated_dir = Path.cwd() / "tests" / "canonicals" / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        for intent_category, failure_reason, count, sessions in patterns:
            # Only generate stubs for patterns with sufficient signal
            if count < 3:
                continue

            stub_code = self.generate_eval_stub(
                intent_category,
                failure_reason,
                count,
                sessions
            )

            # Create filename from pattern
            filename = f"test_{intent_category}_{failure_reason}".lower()
            filename = filename.replace(" ", "_").replace("-", "_")
            # Sanitize
            filename = "".join(c if c.isalnum() or c == "_" else "_" for c in filename)
            filename = f"{filename}.py"

            stub_path = generated_dir / filename

            # Don't overwrite existing stubs (but log that we would)
            if stub_path.exists():
                logger.info(f"Stub already exists: {stub_path}")
            else:
                stub_path.write_text(stub_code)
                logger.info(f"Generated eval stub: {stub_path}")

            self.findings["generated_eval_stubs"].append({
                "pattern": f"{intent_category} / {failure_reason}",
                "count": count,
                "sessions": sessions,
                "stub_path": str(stub_path)
            })

    def generate_report(self, patterns: List[Tuple[str, str, int, int]]) -> str:
        """Generate human-readable failure clustering report."""
        report = []
        report.append("# Failure Clusters (Last 7 Days)\n")

        # Status and context
        report.append(f"**Generated:** {self.findings['timestamp']}")
        report.append(f"**Analysis Window:** {self.findings['analysis_window_days']} days")
        report.append(f"**Total Audit Entries:** {self.findings['total_audit_entries']}")
        report.append(f"**Failure Entries:** {self.findings['failure_entries_count']}\n")

        # Handle insufficient data
        if self.findings["status"] == "insufficient_data":
            report.append("## Status: Insufficient Data\n")
            report.append(f"Reason: {self.findings['message']}\n")
            report.append("The audit_log is empty or has fewer than 10 failure entries. ")
            report.append("No patterns identified. Data collection continues.\n")
            return "\n".join(report)

        # Handle errors
        if self.findings["status"] == "error":
            report.append("## Status: Error\n")
            report.append(f"Error: {self.findings['message']}\n")
            return "\n".join(report)

        # Main analysis
        if not patterns:
            report.append("## Status: No Failures\n")
            report.append("No failures detected in the last 7 days. ")
            report.append("The agent is operating successfully! 🎉\n")
            return "\n".join(report)

        report.append("## Top Failure Patterns\n")

        for intent_category, failure_reason, count, sessions in patterns:
            report.append(
                f"### {intent_category} / {failure_reason}"
            )
            report.append(f"- **Occurrences:** {count}")
            report.append(f"- **Sessions Affected:** {sessions}")
            report.append(f"- **Rate:** {count / max(1, self.findings['failure_entries_count']) * 100:.1f}% of failures")
            report.append("")

        # Generated stubs
        if self.findings["generated_eval_stubs"]:
            report.append("## Generated Eval Case Stubs")
            report.append("The following eval case stubs have been generated for patterns with count ≥ 3. ")
            report.append("Review and adjust assertions before promoting to canonical tests.")
            report.append("")

            for stub_info in self.findings["generated_eval_stubs"]:
                report.append(f"- **{stub_info['pattern']}** ({stub_info['count']} occurrences)")
                report.append(f"  - Location: `{stub_info['stub_path']}`")

        # Recommendations
        report.append("## Recommendations")
        report.append("")

        critical_patterns = [p for p in patterns if p[2] >= 5]
        if critical_patterns:
            report.append("- **High-priority patterns** (≥5 occurrences) identified:")
            for intent, reason, count, _ in critical_patterns:
                report.append(f"  - {intent} / {reason} ({count}x)")
            report.append("")

        if self.findings["generated_eval_stubs"]:
            report.append("- Review generated eval stubs in `tests/canonicals/generated/`")
            report.append("- Test patterns locally before promoting to canonical tests")
            report.append("- Update baseline_scores.json once promoted")
        else:
            report.append("- Continue monitoring for failure patterns")

        return "\n".join(report)

    def save_reports(self, patterns: List[Tuple[str, str, int, int]]) -> Tuple[Path, Path]:
        """Save markdown and JSON reports."""
        output_dir = Path.cwd() / "logs"
        output_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")

        # Markdown report
        report_content = self.generate_report(patterns)
        md_path = output_dir / f"failure_clusters_{today}.md"
        md_path.write_text(report_content)
        logger.info(f"Markdown report saved to {md_path}")

        # JSON report (structured for downstream consumption)
        self.findings["failure_patterns"] = [
            {
                "intent_category": p[0],
                "failure_reason": p[1],
                "count": p[2],
                "sessions": p[3]
            }
            for p in patterns
        ]

        json_path = output_dir / f"failure_clusters_{today}.json"
        json_path.write_text(json.dumps(self.findings, indent=2))
        logger.info(f"JSON report saved to {json_path}")

        return md_path, json_path

    def run(self) -> Tuple[Path, Path]:
        """Run full failure clustering analysis."""
        logger.info("Starting failure clustering analysis...")

        # Query patterns
        patterns = self.query_failure_patterns()

        # Generate eval stubs for patterns with count >= 3
        self.generate_eval_stubs(patterns)

        # Save reports
        md_path, json_path = self.save_reports(patterns)

        return md_path, json_path


def main():
    """Run failure clustering and save reports."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    analyzer = FailureClusteringAnalyzer()
    md_path, json_path = analyzer.run()

    print(f"✅ Failure clustering complete:")
    print(f"   Markdown: {md_path}")
    print(f"   JSON: {json_path}")


if __name__ == "__main__":
    main()
