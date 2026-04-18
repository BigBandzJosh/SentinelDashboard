"""
Yahoo Finance Fetcher — Live market data
No API key required (unofficial endpoint).
"""

import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OSINT-Terminal/1.0)",
    "Accept":     "application/json",
}

TICKERS = {
    "indices": [
        ("^GSPC",  "S&P 500"),
        ("^DJI",   "Dow Jones"),
        ("^IXIC",  "NASDAQ"),
        ("^VIX",   "VIX Fear Index"),
        ("^FTSE",  "FTSE 100"),
        ("^N225",  "Nikkei 225"),
    ],
    "crypto": [
        ("BTC-USD", "Bitcoin"),
        ("ETH-USD", "Ethereum"),
    ],
    "energy": [
        ("CL=F",  "Crude Oil (WTI)"),
        ("BZ=F",  "Brent Crude"),
        ("NG=F",  "Natural Gas"),
        ("UX=F",  "Uranium"),
    ],
    "commodities": [
        ("GC=F",  "Gold"),
        ("SI=F",  "Silver"),
        ("HG=F",  "Copper"),
        ("ZW=F",  "Wheat"),
    ],
    "fx": [
        ("DX-Y.NYB", "US Dollar Index"),
        ("EURUSD=X", "EUR/USD"),
        ("CADUSD=X", "CAD/USD"),
    ],
}

# Flatten for parallel fetching
_ALL_TICKERS = []
for _cat, _items in TICKERS.items():
    for _sym, _lbl in _items:
        _ALL_TICKERS.append((_cat, _sym, _lbl))


def _fetch_quote(symbol: str) -> dict | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "1d"}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        price        = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
        prev         = meta.get("previousClose")      or meta.get("chartPreviousClose")
        change       = round(price - prev, 4) if (price and prev) else 0
        change_pct   = round((change / prev) * 100, 2) if prev else 0
        return {
            "price":      round(price, 4) if price else None,
            "prev":       round(prev, 4)  if prev  else None,
            "change":     change,
            "change_pct": change_pct,
            "currency":   meta.get("currency", "USD"),
        }
    except Exception:
        return None


def fetch_yahoo() -> dict:
    markets = {cat: [] for cat in TICKERS}

    # Fetch all 19 tickers in parallel
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_fetch_quote, sym): (cat, sym, lbl)
            for cat, sym, lbl in _ALL_TICKERS
        }
        for future in as_completed(futures):
            cat, sym, lbl = futures[future]
            q = future.result()
            if q:
                markets[cat].append({"symbol": sym, "label": lbl, **q})

    # Preserve display order within each category
    ticker_order = {sym: i for i, (_, sym, _) in enumerate(_ALL_TICKERS)}
    for cat in markets:
        markets[cat].sort(key=lambda x: ticker_order.get(x["symbol"], 99))

    # Compute simple risk summary
    vix_data = next((x for x in markets.get("indices", []) if x["symbol"] == "^VIX"), None)
    vix      = vix_data["price"] if vix_data else None
    risk_level = "LOW"
    if vix:
        if vix >= 30:   risk_level = "HIGH"
        elif vix >= 20: risk_level = "ELEVATED"
        elif vix >= 15: risk_level = "MODERATE"

    return {
        "markets":    markets,
        "vix":        vix,
        "risk_level": risk_level,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     "Yahoo Finance (unofficial)",
    }
