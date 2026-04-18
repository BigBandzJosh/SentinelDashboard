"""
FRED Fetcher — Federal Reserve Economic Data
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html
Set FRED_API_KEY in .env
Without a key: returns empty (FRED requires registration, it's instant/free)
"""

import os, requests
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

FRED_KEY = os.environ.get("FRED_API_KEY", "")
BASE     = "https://api.stlouisfed.org/fred/series/observations"
HEADERS  = {"User-Agent": "OSINT-Terminal/1.0"}

SERIES = {
    "FEDFUNDS":   "Fed Funds Rate (%)",
    "CPIAUCSL":   "CPI (Inflation)",
    "UNRATE":     "Unemployment Rate (%)",
    "T10Y2Y":     "10Y-2Y Yield Spread",
    "BAMLH0A0HYM2":"High Yield Spread (OAS)",
    "DCOILWTICO": "WTI Crude Oil Price",
    "DEXCAUS":    "CAD/USD Exchange Rate",
    "GFDEGDQ188S":"Federal Debt % GDP",
}


def _fetch_series(series_id: str, label: str, since: str) -> dict:
    params = {
        "series_id":        series_id,
        "api_key":          FRED_KEY,
        "file_type":        "json",
        "observation_start": since,
        "sort_order":       "desc",
        "limit":            2,
    }
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    obs  = data.get("observations", [])
    if not obs:
        return None

    latest = obs[0]
    prev   = obs[1] if len(obs) > 1 else None

    val  = float(latest["value"]) if latest["value"] != "." else None
    pval = float(prev["value"])   if prev and prev["value"] != "." else None
    chg  = round(val - pval, 4)   if (val and pval) else None

    return {
        "series":     series_id,
        "label":      label,
        "value":      val,
        "prev":       pval,
        "change":     chg,
        "date":       latest["date"],
        "units":      data.get("units", ""),
    }


def fetch_fred() -> dict:
    if not FRED_KEY:
        return {
            "indicators": [],
            "note": "No FRED API key set. Register free at fred.stlouisfed.org",
            "source": "FRED (no key)",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    since = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    indicators = []

    # Fetch all 8 series in parallel
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_fetch_series, sid, label, since): (sid, label)
            for sid, label in SERIES.items()
        }
        for future in as_completed(futures):
            sid, label = futures[future]
            try:
                result = future.result()
                if result:
                    indicators.append(result)
            except Exception as e:
                indicators.append({
                    "series": sid,
                    "label":  label,
                    "error":  str(e),
                })

    # Preserve original display order
    order = {sid: i for i, sid in enumerate(SERIES)}
    indicators.sort(key=lambda x: order.get(x["series"], 99))

    return {
        "indicators": indicators,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     "FRED API",
    }
