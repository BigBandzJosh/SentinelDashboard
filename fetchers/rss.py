"""
RSS News Fetcher — Aggregates world news from major wire services.
No API key required. No rate limits.
"""

import requests, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fetchers.geo import geocode_headline

HEADERS = {"User-Agent": "OSINT-Terminal/1.0"}

FEEDS = [
    ("BBC World",      "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera",     "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("NPR World",      "https://feeds.npr.org/1004/rss.xml"),
    ("DW News",        "https://rss.dw.com/rdf/rss-en-all"),
    ("CBS World",      "https://www.cbsnews.com/latest/rss/world"),
]


def _parse_feed(name: str, url: str) -> list:
    """Fetch and parse a single RSS feed into event dicts."""
    r = requests.get(url, headers=HEADERS, timeout=12)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    items = root.findall(".//item")
    events = []

    for item in items:
        title   = (item.findtext("title") or "").strip()
        link    = (item.findtext("link") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()

        # Parse categories if present
        categories = [c.text for c in item.findall("category") if c.text]

        # Parse pubDate to ISO format
        ts = ""
        if pub_raw:
            try:
                dt = parsedate_to_datetime(pub_raw)
                ts = dt.isoformat()
            except Exception:
                ts = pub_raw

        if not title:
            continue

        lat, lon = geocode_headline(title, categories, name)

        events.append({
            "title":      title,
            "url":        link,
            "source":     name,
            "timestamp":  ts,
            "categories": categories,
            "lat":        lat,
            "lon":        lon,
        })

    return events


def fetch_rss() -> dict:
    """
    Fetch all RSS feeds in parallel, merge, and sort by timestamp descending.
    Returns the same event structure the dashboard Intelligence Feed expects.
    """
    all_events = []
    sources_ok = []

    with ThreadPoolExecutor(max_workers=len(FEEDS)) as pool:
        futures = {pool.submit(_parse_feed, name, url): name for name, url in FEEDS}
        for future in as_completed(futures):
            name = futures[future]
            try:
                events = future.result()
                all_events.extend(events)
                sources_ok.append(name)
            except Exception:
                pass

    # Sort by timestamp descending (newest first)
    all_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    return {
        "events":     all_events,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     f"RSS ({len(sources_ok)}/{len(FEEDS)} feeds)",
        "feeds_ok":   sources_ok,
    }
