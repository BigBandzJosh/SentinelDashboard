"""
ReliefWeb Fetcher — UN humanitarian situation reports & alerts
No API key required. https://apidoc.rwlabs.org
"""

import requests
from datetime import datetime, timezone

HEADERS = {"User-Agent": "OSINT-Terminal/1.0"}
BASE    = "https://api.reliefweb.int/v1"


def fetch_reliefweb() -> dict:
    alerts    = _fetch_disasters()
    reports   = _fetch_reports()

    return {
        "alerts":     alerts,
        "reports":    reports,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     "ReliefWeb API (UN OCHA)",
    }


def _fetch_disasters() -> list:
    payload = {
        "limit": 30,
        "sort":  ["date:desc"],
        "fields": {
            "include": ["name", "date", "type", "status", "country", "glide"]
        },
        "filter": {
            "field": "status",
            "value": ["alert", "ongoing"],
        }
    }
    try:
        r = requests.post(f"{BASE}/disasters", json=payload, headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return []

    results = []
    for item in (data.get("data") or []):
        f = item.get("fields", {})
        countries = f.get("country", [])
        country_names = [c.get("name", "") for c in countries] if isinstance(countries, list) else []

        dtype = f.get("type", [])
        type_name = dtype[0].get("name", "") if isinstance(dtype, list) and dtype else str(dtype)

        results.append({
            "id":       item.get("id", ""),
            "name":     f.get("name", ""),
            "status":   f.get("status", ""),
            "type":     type_name,
            "glide":    f.get("glide", ""),
            "date":     (f.get("date") or {}).get("created", ""),
            "countries": country_names,
        })
    return results


def _fetch_reports() -> list:
    payload = {
        "limit": 20,
        "sort":  ["date.created:desc"],
        "fields": {
            "include": ["title", "date", "country", "source", "url"]
        },
        "filter": {
            "operator": "AND",
            "conditions": [
                {"field": "format.name", "value": "Situation Report"},
            ]
        }
    }
    try:
        r = requests.post(f"{BASE}/reports", json=payload, headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return []

    results = []
    for item in (data.get("data") or []):
        f = item.get("fields", {})
        countries = f.get("country", [])
        country_names = [c.get("name", "") for c in countries] if isinstance(countries, list) else []
        sources = f.get("source", [])
        source_names = [s.get("name", "") for s in sources] if isinstance(sources, list) else []

        results.append({
            "title":     f.get("title", ""),
            "date":      (f.get("date") or {}).get("created", ""),
            "countries": country_names,
            "sources":   source_names,
            "url":       f.get("url", ""),
        })
    return results
