"""
NASA FIRMS Fetcher
Satellite fire/thermal hotspot detection.
Free API key: https://firms.modaps.eosdis.nasa.gov/api/
Set FIRMS_MAP_KEY in .env — works without key but rate-limited.
Optional: set FIRMS_BBOX=west,south,east,north to filter by bounding box.
Optional: set FIRMS_DAYS=1-10 lookback window (default 2).
"""

import os, csv, io, requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

FIRMS_KEY = os.environ.get("FIRMS_MAP_KEY", "")
HEADERS   = {"User-Agent": "OSINT-Terminal/1.0"}

# Multiple satellite sources for better temporal coverage
SOURCES = ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT"]


def _parse_bbox(bbox_str: str):
    """Parse 'west,south,east,north' into a tuple of floats, or None."""
    if not bbox_str:
        return None
    parts = bbox_str.split(",")
    if len(parts) != 4:
        return None
    try:
        return tuple(float(p.strip()) for p in parts)
    except ValueError:
        return None


def _in_bbox(lat: float, lon: float, bbox: tuple) -> bool:
    """Check if a point falls within (west, south, east, north)."""
    west, south, east, north = bbox
    return south <= lat <= north and west <= lon <= east


def _fetch_source(source: str, area: str, days: int) -> str:
    """Fetch CSV text from a single FIRMS source."""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_KEY}/{source}/{area}/{days}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def _parse_csv(text: str, bbox, filter_bbox: bool) -> list:
    """Parse FIRMS CSV into fire dicts, optionally filtering by bbox."""
    fires = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        try:
            lat  = float(row.get("latitude")  or row.get("lat", 0))
            lon  = float(row.get("longitude") or row.get("lon", 0))
            frp  = float(row.get("frp", 0))
            conf = row.get("confidence", "n")
        except (TypeError, ValueError):
            continue

        if filter_bbox and bbox and not _in_bbox(lat, lon, bbox):
            continue

        fires.append({
            "lat":        lat,
            "lon":        lon,
            "frp":        frp,
            "confidence": conf,
            "acq_date":   row.get("acq_date", ""),
            "acq_time":   row.get("acq_time", ""),
            "satellite":  row.get("satellite", row.get("instrument", "")),
        })
    return fires


def fetch_firms() -> dict:
    """
    Pull fire detections from multiple FIRMS satellite sources in parallel.
    Reads FIRMS_BBOX and FIRMS_DAYS env vars at call time.
    """
    bbox_str = os.environ.get("FIRMS_BBOX", "").strip()
    bbox = _parse_bbox(bbox_str)
    days = int(os.environ.get("FIRMS_DAYS", "2"))
    days = max(1, min(days, 10))

    if FIRMS_KEY:
        area = bbox_str if bbox else "world"
        all_fires = []
        sources_ok = []

        with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
            futures = {pool.submit(_fetch_source, src, area, days): src for src in SOURCES}
            for future in as_completed(futures):
                src = futures[future]
                try:
                    text = future.result()
                    fires = _parse_csv(text, bbox, filter_bbox=False)
                    all_fires.extend(fires)
                    sources_ok.append(src)
                except Exception:
                    pass  # individual source failure is fine, others still contribute

        fires = all_fires
    else:
        # Public no-key endpoint — single global CSV, filter client-side
        url = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            fires = _parse_csv(r.text, bbox, filter_bbox=True)
            sources_ok = ["NOAA20_PUBLIC"]
        except Exception as e:
            return {"fires": [], "error": str(e), "source": "NASA FIRMS"}

    # Sort by intensity descending, cap at 2000 for map performance
    fires.sort(key=lambda x: x["frp"], reverse=True)
    fires = fires[:2000]

    return {
        "fires":      fires,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     f"NASA FIRMS ({', '.join(sources_ok)})",
        "key_used":   bool(FIRMS_KEY),
        "bbox":       bbox_str or "world",
        "days":       days,
    }
