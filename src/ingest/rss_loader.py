"""RSS feed loader: reads rss_sources.csv, validates feeds, fetches articles."""

import csv
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

from src.config import RSS_SOURCE_FILE, DATA_DIR, NEWS_FETCH_LIMIT, ARTICLE_TIMEOUT

logger = logging.getLogger(__name__)


def load_rss_sources(csv_path: Path | None = None) -> list[dict]:
    """Load and parse rss_sources.csv."""
    path = csv_path or RSS_SOURCE_FILE
    sources = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sources.append(row)
    logger.info("Loaded %d RSS sources from %s", len(sources), path)
    return sources


def validate_feed(url: str, timeout: int = 10) -> tuple[bool, str]:
    """Check if an RSS feed URL is alive. Returns (alive, reason)."""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "OntologyEngine/1.0 (Research; +https://example.com)"
        })
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            return False, f"Parse error: {feed.bozo_exception}"
        if len(feed.entries) == 0:
            return False, "No entries found"
        return True, f"{len(feed.entries)} entries"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection error"
    except Exception as e:
        return False, str(e)


def validate_all_feeds(sources: list[dict] | None = None) -> list[dict]:
    """Validate all feeds and produce validation results."""
    if sources is None:
        sources = load_rss_sources()

    results = []
    now = datetime.now(timezone.utc).isoformat()

    for src in sources:
        url = src.get("rss_url", "")
        name = src.get("source_name", "")
        logger.info("Validating %s: %s", name, url)

        alive, reason = validate_feed(url)
        result = {**src, "alive": alive, "validation_reason": reason, "last_checked": now}
        results.append(result)

        if alive:
            logger.info("  ✓ %s — %s", name, reason)
        else:
            logger.warning("  ✗ %s — %s", name, reason)

        time.sleep(0.5)  # polite rate limiting

    return results


def save_validation_csv(results: list[dict], path: Path | None = None) -> Path:
    """Save validation results to CSV."""
    path = path or (DATA_DIR / "rss_validation.csv")
    if not results:
        return path

    fieldnames = list(results[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    logger.info("Saved validation to %s", path)
    return path


def fetch_articles_from_feed(
    feed_url: str,
    limit: int | None = None,
) -> list[dict]:
    """Fetch article entries from a single RSS feed."""
    limit = limit or NEWS_FETCH_LIMIT
    try:
        resp = requests.get(feed_url, timeout=ARTICLE_TIMEOUT, headers={
            "User-Agent": "OntologyEngine/1.0"
        })
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:limit]:
            articles.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "source_feed": feed_url,
            })
        return articles
    except Exception as e:
        logger.error("Failed to fetch from %s: %s", feed_url, e)
        return []


def fetch_articles_from_all_feeds(
    sources: list[dict] | None = None,
    limit_per_feed: int = 5,
) -> list[dict]:
    """Fetch articles from all alive feeds."""
    if sources is None:
        sources = load_rss_sources()

    all_articles = []
    for src in sources:
        url = src.get("rss_url", "")
        name = src.get("source_name", "")
        # Skip known-dead feeds
        if src.get("alive") == "False" or src.get("alive") is False:
            continue

        logger.info("Fetching from %s", name)
        articles = fetch_articles_from_feed(url, limit=limit_per_feed)
        for a in articles:
            a["source_name"] = name
            a["category"] = src.get("category", "")
            a["credibility_score"] = src.get("credibility_score", "0")
        all_articles.extend(articles)
        time.sleep(0.3)

    logger.info("Fetched %d total articles", len(all_articles))
    return all_articles


def load_sample_articles(sample_dir: Path | None = None) -> list[dict]:
    """Load fallback sample articles from data/sample_news/."""
    from src.config import SAMPLE_NEWS_DIR
    import json

    sample_dir = sample_dir or SAMPLE_NEWS_DIR
    articles = []
    if not sample_dir.exists():
        return articles

    for f in sorted(sample_dir.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    articles.extend(data)
                else:
                    articles.append(data)
        except Exception as e:
            logger.warning("Failed to load sample %s: %s", f, e)

    logger.info("Loaded %d sample articles from %s", len(articles), sample_dir)
    return articles
