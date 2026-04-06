#!/usr/bin/env python3
"""
Fetch items from configured digest sources (HackerNews, arXiv, CISA KEV, RSS).

Stores fetched items in digest_items table for subsequent filtering.
"""

import json
import logging
import sqlite3
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from hermes_state import SessionDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_hackernews(url: str, limit=20):
    """Fetch top HackerNews stories."""
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            story_ids = json.loads(response.read().decode('utf-8'))[:limit]

        for sid in story_ids:
            try:
                story_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                req = urllib.request.Request(story_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    story = json.loads(response.read().decode('utf-8'))
                    if story and story.get('type') == 'story':
                        items.append({
                            'id': f"hn_{sid}",
                            'source': 'HackerNews',
                            'type': 'story',
                            'title': story.get('title', ''),
                            'url': story.get('url', f"https://news.ycombinator.com/item?id={sid}"),
                            'content': story.get('text', '')
                        })
            except Exception as e:
                logger.debug(f"Error fetching HN item {sid}: {e}")
    except Exception as e:
        logger.error(f"Error fetching HackerNews top stories: {e}")
    return items


def fetch_arxiv(url: str):
    """Fetch recent arXiv papers via Atom feed."""
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            root = ET.fromstring(response.read().decode('utf-8'))

            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                try:
                    aid = entry.find('atom:id', ns).text.split('/')[-1]
                    title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                    summary = entry.find('atom:summary', ns).text.strip()
                    url_link = entry.find('atom:id', ns).text

                    items.append({
                        'id': f"arxiv_{aid}",
                        'source': 'arXiv',
                        'type': 'paper',
                        'title': title,
                        'url': url_link,
                        'content': summary
                    })
                except Exception as e:
                    logger.debug(f"Error parsing arXiv entry: {e}")
    except Exception as e:
        logger.error(f"Error fetching arXiv: {e}")
    return items


def fetch_cisa_kev(url: str):
    """Fetch CISA Known Exploited Vulnerabilities from JSON."""
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            vulnerabilities = data.get('vulnerabilities', [])

            # Sort by date added, newest first
            vulnerabilities.sort(key=lambda x: x.get('dateAdded', ''), reverse=True)

            # Take recent ones (top 20)
            for vuln in vulnerabilities[:20]:
                cve_id = vuln.get('cveID')
                items.append({
                    'id': f"cisa_{cve_id}",
                    'source': 'CISA KEV',
                    'type': 'vulnerability',
                    'title': f"{cve_id}: {vuln.get('vulnerabilityName', '')}",
                    'url': f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    'content': vuln.get('shortDescription', '')
                })
    except Exception as e:
        logger.error(f"Error fetching CISA KEV: {e}")
    return items


def main():
    """Load sources config and fetch items."""
    config_path = Path(__file__).parent.parent / "config" / "digest_sources.json"
    if not config_path.exists():
        logger.error(f"Config file not found at {config_path}")
        return

    with open(config_path) as f:
        config = json.load(f)

    db = SessionDB()
    all_items = []

    for source in config.get('sources', []):
        if not source.get('enabled'):
            continue

        logger.info(f"Fetching from {source['name']}...")
        if source['id'] == 'hackernews':
            all_items.extend(fetch_hackernews(source['url']))
        elif source['id'] == 'arxiv':
            all_items.extend(fetch_arxiv(source['url']))
        elif source['id'] == 'cisa_kev':
            all_items.extend(fetch_cisa_kev(source['url']))

    logger.info(f"Fetched {len(all_items)} total items. Inserting into database...")

    def _insert_items(conn):
        count = 0
        for item in all_items:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO digest_items
                       (id, source, type, title, url, content, fetched_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (
                        item['id'],
                        item['source'],
                        item['type'],
                        item['title'],
                        item['url'],
                        item['content'],
                        time.time()
                    )
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    count += 1
            except sqlite3.Error as e:
                logger.error(f"Database error inserting {item['id']}: {e}")
        return count

    inserted = db._execute_write(_insert_items)
    logger.info(f"Successfully inserted {inserted} new items into digest_items.")
    db.close()


if __name__ == "__main__":
    main()
