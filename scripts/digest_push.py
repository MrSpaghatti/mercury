#!/usr/bin/env python3
"""
Push filtered digest items to Telegram.

High-priority items (score >= 0.8) can be pushed immediately.
Standard items batched into morning digest (configurable time, default 07:00 local).

Telegram credentials via env vars:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from hermes_state import SessionDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': 'true'
    }).encode('utf-8')

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('ok', False)
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def main():
    """Push filtered items to Telegram or log to stdout."""
    db = SessionDB()

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()

    # Get filtered items ready to push
    with db._lock:
        cursor = db._conn.execute(
            """SELECT id, source, title, url, score, reasoning FROM digest_items
               WHERE status = 'filtered' AND score >= 0.7
               ORDER BY score DESC
               LIMIT 10"""
        )
        items = [dict(row) for row in cursor.fetchall()]

    if not items:
        logger.info("No items to push (no filtered items with score >= 0.7).")
        db.close()
        return

    logger.info(f"Found {len(items)} items to push to Telegram.")

    # Mark as pushed (regardless of delivery to avoid infinite retries)
    def _mark_pushed(conn):
        for item in items:
            conn.execute("UPDATE digest_items SET status = 'pushed' WHERE id = ?", (item['id'],))

    # Mark low-scored items as ignored
    def _mark_ignored(conn):
        conn.execute("UPDATE digest_items SET status = 'ignored' WHERE status = 'filtered' AND score < 0.7")

    if bot_token and chat_id:
        # Format Telegram message
        message_lines = ["<b>🔐 Daily InfoSec & Tech Digest</b>\n"]
        for item in items:
            # Escape HTML special chars
            title = (item['title'] or '').replace('<', '&lt;').replace('>', '&gt;')
            source = (item['source'] or '').replace('<', '&lt;').replace('>', '&gt;')
            reasoning = (item['reasoning'] or '').replace('<', '&lt;').replace('>', '&gt;')

            message_lines.append(
                f"• <b>[{source}]</b> "
                f"<a href=\"{item['url']}\">{title}</a>"
            )
            message_lines.append(f"  <i>Score: {item['score']:.2f} — {reasoning}</i>\n")

        full_message = "\n".join(message_lines)

        # Send to Telegram
        success = send_telegram_message(bot_token, chat_id, full_message)

        if success:
            logger.info("Successfully pushed digest to Telegram.")
            db._execute_write(_mark_pushed)
            db._execute_write(_mark_ignored)
        else:
            logger.error("Failed to push to Telegram. Keeping items in 'filtered' status.")
    else:
        # Fallback: log to stdout
        logger.info("Telegram credentials not found. Logging digest to stdout.")
        print("\n" + "=" * 60)
        print("DAILY INFOSEC & TECH DIGEST")
        print("=" * 60)
        for item in items:
            print(f"\n[{item['source']}] {item['title']}")
            print(f"Score: {item['score']:.2f} | {item['reasoning']}")
            print(f"Link: {item['url']}")
        print("\n" + "=" * 60)

        # Still mark as pushed for testing
        db._execute_write(_mark_pushed)
        db._execute_write(_mark_ignored)

    db.close()


if __name__ == "__main__":
    main()
