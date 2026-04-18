"""
GDELT Fetcher
Pulls recent geopolitical events from the GDELT 2.0 DOC API.
No API key required. Rate limit: 1 request per 5 seconds.
"""

import requests, time
from datetime import datetime, timezone

HEADERS = {"User-Agent": "OSINT-Terminal/1.0 (personal research tool)"}

DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

MAX_RETRIES = 2
RETRY_DELAY = 6  # seconds — GDELT enforces 1 req per 5s


def fetch_gdelt() -> dict:
    """
    Return recent news events from GDELT DOC 2.0 API.
    Retries once on 429 rate-limit responses.
    """
    params = {
        "query":      "(conflict OR military OR sanctions OR nuclear OR protest OR attack)",
        "mode":       "artlist",
        "maxrecords": 75,
        "format":     "json",
        "timespan":   "24h",
        "sort":       "DateDesc",
    }

    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(DOC_URL, params=params, headers=HEADERS, timeout=15)
            if r.status_code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            continue
    else:
        return {"events": [], "error": str(last_err), "source": "GDELT DOC API"}

    articles = data.get("articles") or []
    events = []
    for a in articles:
        raw_lat = a.get("latitude") or a.get("lat")
        raw_lon = a.get("longitude") or a.get("lon")
        try:
            lat = float(raw_lat) if raw_lat else None
            lon = float(raw_lon) if raw_lon else None
        except (TypeError, ValueError):
            lat, lon = None, None

        events.append({
            "lat":       lat,
            "lon":       lon,
            "title":     a.get("title", ""),
            "url":       a.get("url", ""),
            "source":    a.get("domain", ""),
            "tone":      a.get("tone", 0),
            "timestamp": a.get("seendate", ""),
        })

    return {
        "events": events,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "GDELT 2.0 DOC API",
    }
