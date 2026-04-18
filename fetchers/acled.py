"""
ACLED Fetcher — Armed Conflict Location & Event Data
Free researcher key: https://acleddata.com/register/
Set ACLED_KEY and ACLED_EMAIL in .env
Without a key: returns empty (ACLED requires registration)
"""

import os, requests
from datetime import datetime, timezone, timedelta

ACLED_KEY   = os.environ.get("ACLED_KEY", "")
ACLED_EMAIL = os.environ.get("ACLED_EMAIL", "")
HEADERS     = {"User-Agent": "OSINT-Terminal/1.0"}

EVENT_COLORS = {
    "Battles":                     "#ef4444",   # red
    "Explosions/Remote violence":  "#f97316",   # orange
    "Violence against civilians":  "#dc2626",   # dark red
    "Protests":                    "#3b82f6",   # blue
    "Riots":                       "#8b5cf6",   # purple
    "Strategic developments":      "#6b7280",   # grey
}


def fetch_acled() -> dict:
    if not ACLED_KEY or not ACLED_EMAIL:
        return {
            "conflicts": _get_fallback_conflicts(),
            "note": "No ACLED key set — using curated static fallback. Register free at acleddata.com",
            "source": "ACLED (fallback)",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    params = {
        "key":         ACLED_KEY,
        "email":       ACLED_EMAIL,
        "event_date":  since,
        "event_date_where": "BETWEEN",
        "event_date2": datetime.now().strftime("%Y-%m-%d"),
        "limit":       500,
        "fields":      "event_date|event_type|sub_event_type|actor1|country|latitude|longitude|fatalities|notes",
        "format":      "json",
    }

    try:
        r = requests.get("https://api.acleddata.com/acled/read", params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {"conflicts": [], "error": str(e), "source": "ACLED"}

    conflicts = []
    for row in (data.get("data") or []):
        try:
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
        except (TypeError, ValueError):
            continue

        etype = row.get("event_type", "")
        conflicts.append({
            "lat":        lat,
            "lon":        lon,
            "type":       etype,
            "sub_type":   row.get("sub_event_type", ""),
            "actor":      row.get("actor1", ""),
            "country":    row.get("country", ""),
            "fatalities": int(row.get("fatalities", 0) or 0),
            "date":       row.get("event_date", ""),
            "notes":      (row.get("notes", "") or "")[:200],
            "color":      EVENT_COLORS.get(etype, "#6b7280"),
        })

    return {
        "conflicts":  conflicts,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     "ACLED Live API",
    }


def _get_fallback_conflicts():
    """
    Static sample of known active conflict zones when no API key.
    Updated manually — replace with ACLED key for live data.
    """
    return [
        {"lat": 48.5,  "lon": 37.5,  "type": "Battles", "country": "Ukraine", "color": "#ef4444", "notes": "Eastern Ukraine conflict zone"},
        {"lat": 15.5,  "lon": 32.5,  "type": "Battles", "country": "Sudan", "color": "#ef4444", "notes": "Sudan civil conflict"},
        {"lat": 31.5,  "lon": 34.8,  "type": "Explosions/Remote violence", "country": "Gaza", "color": "#f97316", "notes": "Gaza conflict zone"},
        {"lat": 14.0,  "lon": 43.0,  "type": "Battles", "country": "Yemen", "color": "#ef4444", "notes": "Yemen civil war"},
        {"lat": 6.5,   "lon": 20.5,  "type": "Violence against civilians", "country": "DRC", "color": "#dc2626", "notes": "Eastern DRC armed groups"},
        {"lat": 9.0,   "lon": 38.5,  "type": "Battles", "country": "Ethiopia", "color": "#ef4444", "notes": "Amhara region conflict"},
        {"lat": 33.5,  "lon": 43.5,  "type": "Explosions/Remote violence", "country": "Iraq", "color": "#f97316", "notes": "ISIS remnant activity"},
        {"lat": 35.0,  "lon": 38.5,  "type": "Battles", "country": "Syria", "color": "#ef4444", "notes": "Ongoing Syria conflict"},
        {"lat": 13.5,  "lon": 2.1,   "type": "Battles", "country": "Mali", "color": "#ef4444", "notes": "Sahel insurgency"},
        {"lat": 12.3,  "lon": 43.1,  "type": "Strategic developments", "country": "Djibouti", "color": "#6b7280", "notes": "Red Sea security developments"},
        {"lat": 51.5,  "lon": 59.5,  "type": "Strategic developments", "country": "Russia/Kazakhstan border", "color": "#6b7280", "notes": "Military activity"},
        {"lat": 23.0,  "lon": 89.0,  "type": "Protests", "country": "Bangladesh", "color": "#3b82f6", "notes": "Political unrest"},
    ]
