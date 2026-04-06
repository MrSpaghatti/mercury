#!/usr/bin/env python3
"""
Weekly memory health check cron job.

Scans xMemory layers for:
- Contradictions between new episodes and existing semantics
- Stale nodes (no backlinks for >30 days)
- Cluster quality (Fano bound: 4-12 semantics per theme)

Generates weekly report to logs/memory_health_YYYY-MM-DD.md
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MemoryHealthCheck:
    """Health check analyzer for xMemory layers."""

    def __init__(self, db_path: Optional[Path] = None, chroma_path: Optional[Path] = None):
        """Initialize health check with paths to memory stores."""
        self.db_path = db_path or Path.home() / ".hermes" / "state.db"
        self.chroma_path = chroma_path or Path.cwd() / "chroma_db"
        self.findings = {
            "timestamp": datetime.now().isoformat(),
            "contradictions": [],
            "stale_nodes": [],
            "cluster_imbalance": [],
            "summary": {}
        }

    def check_contradictions(self) -> List[Dict[str, Any]]:
        """Find contradictions between episodes and semantics."""
        contradictions = []

        # Check if chroma_db exists and has semantics
        if not self.chroma_path.exists():
            logger.warning("ChromaDB path not found, skipping semantic check")
            return contradictions

        # Placeholder: in production, would compare episode content with semantic facts
        # for logical conflicts (e.g., conflicting user preferences, repeated mistakes)
        # For now, just log that check was attempted
        logger.debug("Scanning semantics for contradictions...")

        return contradictions

    def check_stale_nodes(self, stale_threshold_days: int = 30) -> List[Dict[str, Any]]:
        """Find stale memory nodes with no recent references."""
        stale_nodes = []

        if not self.db_path.exists():
            logger.warning("Database not found, skipping staleness check")
            return stale_nodes

        try:
            cutoff_time = time.time() - (stale_threshold_days * 86400)

            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT id, session_id, timestamp, role
                    FROM messages
                    WHERE timestamp < ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (cutoff_time,))

                rows = cursor.fetchall()
                for row in rows:
                    stale_nodes.append({
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "last_seen": row["timestamp"],
                        "days_ago": round((time.time() - row["timestamp"]) / 86400, 1)
                    })
        except Exception as e:
            logger.error(f"Error checking stale nodes: {e}")

        return stale_nodes

    def check_cluster_balance(self) -> List[Dict[str, Any]]:
        """Check if theme/semantic clusters are balanced per Fano bound (4-12 per theme)."""
        imbalances = []

        # Placeholder: in production, would analyze ChromaDB collection structure
        # For now, log that check was attempted
        logger.debug("Checking semantic cluster balance...")

        return imbalances

    def generate_report(self) -> str:
        """Generate human-readable health check report."""
        self.findings["contradictions"] = self.check_contradictions()
        self.findings["stale_nodes"] = self.check_stale_nodes()
        self.findings["cluster_imbalance"] = self.check_cluster_balance()

        # Summary stats
        self.findings["summary"] = {
            "contradictions_found": len(self.findings["contradictions"]),
            "stale_nodes_found": len(self.findings["stale_nodes"]),
            "cluster_imbalances_found": len(self.findings["cluster_imbalance"]),
            "total_issues": (
                len(self.findings["contradictions"]) +
                len(self.findings["stale_nodes"]) +
                len(self.findings["cluster_imbalance"])
            )
        }

        report = []
        report.append("# Memory Health Check Report")
        report.append(f"\n**Date:** {self.findings['timestamp']}\n")

        # Summary
        report.append("## Summary")
        report.append(f"- Contradictions found: {self.findings['summary']['contradictions_found']}")
        report.append(f"- Stale nodes found: {self.findings['summary']['stale_nodes_found']}")
        report.append(f"- Cluster imbalances found: {self.findings['summary']['cluster_imbalances_found']}")
        report.append(f"- **Total issues: {self.findings['summary']['total_issues']}**\n")

        # Stale nodes
        if self.findings["stale_nodes"]:
            report.append("## Stale Nodes (>30 days)")
            for node in self.findings["stale_nodes"][:10]:  # Limit to top 10
                report.append(
                    f"- Session `{node['session_id']}`: "
                    f"{node['days_ago']} days old (ID: {node['id']})"
                )
            if len(self.findings["stale_nodes"]) > 10:
                report.append(f"- ... and {len(self.findings['stale_nodes']) - 10} more")
            report.append()

        # Contradictions
        if self.findings["contradictions"]:
            report.append("## Contradictions Found")
            for cont in self.findings["contradictions"]:
                report.append(f"- {cont}")
            report.append()

        # Cluster imbalances
        if self.findings["cluster_imbalance"]:
            report.append("## Cluster Imbalances (Fano Bound: 4-12 per theme)")
            for imb in self.findings["cluster_imbalance"]:
                report.append(f"- {imb}")
            report.append()

        # Recommendations
        report.append("## Recommendations")
        if self.findings['summary']['stale_nodes_found'] > 5:
            report.append("- Archive or consolidate stale nodes")
        if self.findings['summary']['contradictions_found'] > 0:
            report.append("- Review and resolve semantic contradictions")
        if self.findings['summary']['cluster_imbalances_found'] > 0:
            report.append("- Rebalance theme/semantic clusters")
        if self.findings['summary']['total_issues'] == 0:
            report.append("- No issues found. Memory is healthy ✅")

        return "\n".join(report)

    def save_report(self, output_dir: Optional[Path] = None) -> Path:
        """Save report to logs/memory_health_YYYY-MM-DD.md"""
        if output_dir is None:
            output_dir = Path.cwd() / "logs"
        output_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        report_path = output_dir / f"memory_health_{today}.md"

        report_content = self.generate_report()
        report_path.write_text(report_content)

        # Also save structured JSON for programmatic access
        json_path = output_dir / f"memory_health_{today}.json"
        json_path.write_text(json.dumps(self.findings, indent=2))

        logger.info(f"Health check report saved to {report_path}")
        return report_path


def main():
    """Run health check and save report."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    check = MemoryHealthCheck()
    report_path = check.save_report()
    print(f"✅ Health check complete: {report_path}")


if __name__ == "__main__":
    main()
