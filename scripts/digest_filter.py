#!/usr/bin/env python3
"""
Filter digest items by relevance score using ModelProvider.

Scores each pending item 0.0–1.0 against interest profile (infosec, systems,
AI/ML, homelab). Items below 0.5 dropped. Items above 0.8 flagged high-priority.

ModelProvider supports LOCAL_MODEL_ENDPOINT env var for local inference or
OPENROUTER_API_KEY for remote inference.
"""

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from hermes_state import SessionDB
from agent.model_provider import ModelProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI assistant helping a software engineer filter news and papers.
Evaluate the given item and score its relevance from 0.0 to 1.0.
High relevance (0.7-1.0): InfoSec vulnerabilities (CISA KEV), major AI/LLM breakthroughs, Python/Go/Rust backend engineering, cryptography, formal methods.
Medium relevance (0.4-0.6): General tech news, data structures, algorithms, other CS papers.
Low relevance (0.0-0.3): Non-tech news, frontend frameworks (React, Vue), marketing, unrelated science.

Output ONLY a JSON object with two keys:
{"score": float between 0.0 and 1.0, "reasoning": "1-2 sentence explanation"}
"""


def extract_json(text: str) -> dict:
    """Extract JSON from model output (may be wrapped in markdown)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass
    return {"score": 0.0, "reasoning": "Failed to parse model output."}


def main():
    """Filter pending digest items by relevance."""
    db = SessionDB()

    # Initialize ModelProvider (respects LOCAL_MODEL_ENDPOINT and OPENROUTER_API_KEY)
    try:
        provider = ModelProvider(
            model_name="google/gemini-3-flash-preview",
            provider="auto"
        )
    except ValueError as e:
        logger.error(f"Failed to initialize ModelProvider: {e}")
        logger.info("Skipping filter (local endpoint or OpenRouter API key needed)")
        return

    # Get pending items
    with db._lock:
        cursor = db._conn.execute(
            "SELECT id, source, type, title, content FROM digest_items WHERE status = 'pending' LIMIT 50"
        )
        items = [dict(row) for row in cursor.fetchall()]

    if not items:
        logger.info("No pending items to filter.")
        db.close()
        return

    logger.info(f"Filtering {len(items)} pending items with ModelProvider (endpoint: {provider.endpoint_type})...")

    filtered_count = 0
    high_priority_count = 0

    for item in items:
        prompt = f"Source: {item['source']}\nType: {item['type']}\nTitle: {item['title']}\n\nContent:\n{item['content'][:500]}"

        try:
            # Score text returns a float 0.0-1.0
            score = provider.score_text(prompt, SYSTEM_PROMPT)

            # Determine status based on score
            if score >= 0.5:
                status = 'filtered'
                reasoning = f"Score: {score:.2f}"
                filtered_count += 1
                if score >= 0.8:
                    high_priority_count += 1
            else:
                status = 'dropped'
                reasoning = f"Below threshold ({score:.2f})"

            # Update DB
            def _update(conn):
                conn.execute(
                    "UPDATE digest_items SET score = ?, reasoning = ?, status = ? WHERE id = ?",
                    (score, reasoning, status, item['id'])
                )

            db._execute_write(_update)
            logger.info(f"Filtered {item['id']}: Score {score:.2f} ({status})")

        except Exception as e:
            logger.error(f"Error filtering item {item['id']}: {e}")

    logger.info(f"Filtering complete. Kept {filtered_count} items, {high_priority_count} flagged high-priority.")
    db.close()


if __name__ == "__main__":
    main()
