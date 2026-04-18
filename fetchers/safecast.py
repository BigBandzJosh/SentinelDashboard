"""
Safecast Fetcher — Citizen science radiation monitoring
No API key required. https://api.safecast.org
"""

import requests
from datetime import datetime, timezone

HEADERS = {"User-Agent": "OSINT-Terminal/1.0"}
BASE    = "https://api.safecast.org/measurements.json"

# Normal background radiation range (uSv/h)
NORMAL_LOW  = 0.05
NORMAL_HIGH = 0.30
ELEVATED    = 0.50
HIGH        = 1.00


def fetch_safecast() -> dict:
    params = {
        "order":     "captured_at desc",
        "per_page":  200,
    }

    try:
        r = requests.get(BASE, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {"readings": [], "error": str(e), "source": "Safecast"}

    readings = []
    for m in (data if isinstance(data, list) else []):
        try:
            lat = float(m.get("latitude")  or 0)
            lon = float(m.get("longitude") or 0)
            val = float(m.get("value")     or 0)   # in CPM or nSv/h depending on device
        except (TypeError, ValueError):
            continue

        if lat == 0 and lon == 0:
            continue

        # Convert to uSv/h (approximate — Safecast units vary by device)
        # Most devices report in CPM; ~151.5 CPM ≈ 1 uSv/h for J305 tube
        unit = m.get("unit", "cpm").lower()
        if "cpm" in unit:
            usv = val / 151.5
        elif "nsv" in unit:
            usv = val / 1000
        else:
            usv = val   # assume already uSv/h

        level = "normal"
        if usv >= HIGH:
            level = "high"
        elif usv >= ELEVATED:
            level = "elevated"
        elif usv >= NORMAL_HIGH:
            level = "slightly_elevated"

        readings.append({
            "lat":          lat,
            "lon":          lon,
            "usv":          round(usv, 4),
            "raw_value":    val,
            "unit":         unit,
            "level":        level,
            "device_id":    m.get("device_id", ""),
            "captured_at":  m.get("captured_at", ""),
        })

    # Sort: elevated readings first
    level_order = {"high": 0, "elevated": 1, "slightly_elevated": 2, "normal": 3}
    readings.sort(key=lambda x: level_order.get(x["level"], 3))

    elevated_count = sum(1 for r in readings if r["level"] in ("elevated", "high"))

    return {
        "readings":       readings,
        "elevated_count": elevated_count,
        "fetched_at":     datetime.now(timezone.utc).isoformat(),
        "source":         "Safecast API",
    }
