"""Quick check: RSS sources and a sample fetch."""
from src.ingest.rss_loader import load_rss_sources, fetch_articles_from_all_feeds

sources = load_rss_sources()
alive = [s for s in sources if s.get("alive", "") != "False"]
print(f"RSS sources: {len(sources)}, Active: {len(alive)}")

# Fetch just 1 article per feed from first 5 feeds to test
print("\nFetching sample articles from first 5 feeds...")
articles = fetch_articles_from_all_feeds(sources=alive[:5], limit_per_feed=1)
print(f"Fetched {len(articles)} articles")
for a in articles[:5]:
    title = a.get("title", "?")[:80]
    link = a.get("link", "?")[:60]
    has_body = bool(a.get("body") or a.get("summary") or a.get("description"))
    print(f"  [{has_body and 'OK' or 'NO BODY'}] {title}")
