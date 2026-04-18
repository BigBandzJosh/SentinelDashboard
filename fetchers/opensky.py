"""
OpenSky Network Fetcher
Real-time flight tracking. No key needed for public data.
Optional: set OPENSKY_USER and OPENSKY_PASS for higher rate limits.
"""

import os, requests
from datetime import datetime, timezone

USER    = os.environ.get("OPENSKY_USER", "")
PASS    = os.environ.get("OPENSKY_PASS", "")
HEADERS = {"User-Agent": "OSINT-Terminal/1.0"}

# Interesting ICAO prefixes for military / special flights
MILITARY_PREFIXES = {
    "AE": "US Military",
    "43": "Russian Military",
    "7F": "Chinese Military",
    "ZZ": "UK Military",
    "43C": "Russian AF",
}


def fetch_opensky() -> dict:
    """
    Pull all airborne aircraft states from OpenSky.
    Filters to a reasonable sample for the map.
    """
    url  = "https://opensky-network.org/api/states/all"
    auth = (USER, PASS) if USER and PASS else None

    try:
        r = requests.get(url, auth=auth, headers=HEADERS, timeout=20)
        if r.status_code == 429:
            return {"flights": [], "error": "Rate limited (OpenSky 429)", "source": "OpenSky"}
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {"flights": [], "error": str(e), "source": "OpenSky"}

    states = data.get("states") or []
    # Columns: icao24, callsign, origin_country, time_position, last_contact,
    #          longitude, latitude, baro_altitude, on_ground, velocity,
    #          true_track, vertical_rate, sensors, geo_altitude, squawk,
    #          spi, position_source
    flights = []
    for s in states:
        try:
            lon = s[5]; lat = s[6]
            if lat is None or lon is None:
                continue
            on_ground = s[8]
            if on_ground:
                continue

            icao     = (s[0] or "").upper()
            callsign = (s[1] or "").strip()
            country  = s[2] or ""
            alt_m    = s[7] or s[13] or 0
            vel_ms   = s[9] or 0
            heading  = s[10] or 0
            squawk   = s[14] or ""

            # Flag military / interesting squawks
            is_military = any(icao.startswith(p) for p in MILITARY_PREFIXES)
            is_emergency = squawk in ("7700", "7600", "7500")

            flights.append({
                "lat":         float(lat),
                "lon":         float(lon),
                "icao":        icao,
                "callsign":    callsign,
                "country":     country,
                "alt_m":       round(float(alt_m), 0) if alt_m else 0,
                "alt_ft":      round(float(alt_m) * 3.28084, 0) if alt_m else 0,
                "speed_kts":   round(float(vel_ms) * 1.944, 0) if vel_ms else 0,
                "heading":     float(heading) if heading else 0,
                "squawk":      squawk,
                "military":    is_military,
                "emergency":   is_emergency,
            })
        except (TypeError, ValueError, IndexError):
            continue

    # Prioritise military/emergency, then sample to 300 for map perf
    priority = [f for f in flights if f["military"] or f["emergency"]]
    regular  = [f for f in flights if not f["military"] and not f["emergency"]]

    # Sample regular flights across grid for global coverage
    import random
    random.seed(42)
    sampled  = random.sample(regular, min(250, len(regular)))
    final    = priority + sampled

    return {
        "flights":         final,
        "total_airborne":  len(flights),
        "military_count":  len(priority),
        "fetched_at":      datetime.now(timezone.utc).isoformat(),
        "source":          "OpenSky Network",
    }
