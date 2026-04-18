"""
CelesTrak Fetcher — Satellite tracking
No API key required. https://celestrak.org
Fetches active satellite counts by category.
"""

import requests
from datetime import datetime, timezone

HEADERS = {"User-Agent": "OSINT-Terminal/1.0"}

CATEGORIES = {
    "stations":       ("Space Stations",       "https://celestrak.org/SOCRATES/query.php?CODE=ISS&FORMAT=JSON"),
    "starlink":       ("Starlink",             "https://celestrak.org/SOCRATES/query.php?CODE=STARLINK&FORMAT=JSON"),
    "military":       ("Military Satellites",  None),   # fetched via supplemental
    "weather":        ("Weather Satellites",   None),
    "recent_launches":("Recent Launches",      "https://celestrak.org/SOCRATES/query.php?CODE=LAUNCH&FORMAT=JSON"),
}

# GP data in JSON from CelesTrak (TLE groups)
GP_URLS = {
    "stations":        "https://celestrak.org/SOCRATES/query.php?CODE=ISS&FORMAT=JSON",
    "starlink":        "https://celestrak.org/gp.php?GROUP=starlink&FORMAT=json",
    "oneweb":          "https://celestrak.org/gp.php?GROUP=oneweb&FORMAT=json",
    "military":        "https://celestrak.org/gp.php?GROUP=military&FORMAT=json",
    "weather":         "https://celestrak.org/gp.php?GROUP=weather&FORMAT=json",
    "recent_launches": "https://celestrak.org/gp.php?GROUP=last-30-days&FORMAT=json",
    "iss":             "https://celestrak.org/gp.php?CATNR=25544&FORMAT=json",
}


def fetch_celestrak() -> dict:
    counts = {}
    iss_info = None
    errors   = []

    for group, url in GP_URLS.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            data = r.json()
            count = len(data) if isinstance(data, list) else 0
            counts[group] = count

            if group == "iss" and isinstance(data, list) and data:
                sat = data[0]
                iss_info = {
                    "name":   sat.get("OBJECT_NAME", "ISS"),
                    "norad":  sat.get("NORAD_CAT_ID", "25544"),
                    "epoch":  sat.get("EPOCH", ""),
                    "period": sat.get("MEAN_MOTION", ""),
                    "inc":    sat.get("INCLINATION", ""),
                }
        except Exception as e:
            counts[group] = 0
            errors.append(f"{group}: {e}")

    satellites = [
        {"name": "Starlink Constellation",  "count": counts.get("starlink", 0),        "type": "commercial",  "operator": "SpaceX"},
        {"name": "OneWeb Constellation",    "count": counts.get("oneweb", 0),           "type": "commercial",  "operator": "OneWeb"},
        {"name": "Military Satellites",     "count": counts.get("military", 0),         "type": "military",    "operator": "Various DoD"},
        {"name": "Weather Satellites",      "count": counts.get("weather", 0),          "type": "weather",     "operator": "NOAA/EUMETSAT"},
        {"name": "Recent Launches (30d)",   "count": counts.get("recent_launches", 0),  "type": "recent",      "operator": "Various"},
        {"name": "ISS",                     "count": 1,                                  "type": "station",     "operator": "NASA/Roscosmos"},
    ]

    return {
        "satellites":   satellites,
        "iss":          iss_info,
        "total_tracked":sum(counts.values()),
        "errors":       errors,
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
        "source":       "CelesTrak",
    }
