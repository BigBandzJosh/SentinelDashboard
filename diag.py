#!/usr/bin/env python3
"""
SENTINEL Diagnostics
Tests each data source and reports status, record counts, and any errors.
Run this before your first sweep to verify connectivity and key configuration.

Usage: python3 diag.py
"""

import os, sys, time, threading
from pathlib import Path

# Load .env first
def load_env(path=".env"):
    p = Path(path)
    if not p.exists():
        p = Path(".env.example")
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip(); val = val.strip()
        if val and not os.environ.get(key):
            os.environ[key] = val

load_env()
sys.path.insert(0, str(Path(__file__).parent))

# ── Colour helpers (works on most terminals) ──────────────────────────────────
GRN  = "\033[92m"
RED  = "\033[91m"
YLW  = "\033[93m"
CYN  = "\033[96m"
DIM  = "\033[2m"
RST  = "\033[0m"
BOLD = "\033[1m"

def ok(msg):   print(f"  {GRN}✓{RST}  {msg}")
def err(msg):  print(f"  {RED}✗{RST}  {msg}")
def warn(msg): print(f"  {YLW}⚠{RST}  {msg}")
def info(msg): print(f"  {CYN}·{RST}  {msg}")


def _count(data):
    if isinstance(data, list): return len(data)
    if isinstance(data, dict):
        for k in ("events","fires","flights","conflicts","readings","satellites","alerts","indicators","reports"):
            if k in data and isinstance(data[k], list):
                return len(data[k])
    return 0


TESTS = [
    ("gdelt",      "GDELT (Geopolitical Events)",        "fetchers.gdelt",      "fetch_gdelt",      False),
    ("firms",      "NASA FIRMS (Satellite Fires)",       "fetchers.firms",      "fetch_firms",      False),
    ("opensky",    "OpenSky (Live Flights)",             "fetchers.opensky",    "fetch_opensky",    False),
    ("acled",      "ACLED (Armed Conflicts)",            "fetchers.acled",      "fetch_acled",      True),
    ("safecast",   "Safecast (Radiation)",               "fetchers.safecast",   "fetch_safecast",   False),
    ("celestrak",  "CelesTrak (Satellites)",             "fetchers.celestrak",  "fetch_celestrak",  False),
    ("yahoo",      "Yahoo Finance (Markets)",            "fetchers.yahoo",      "fetch_yahoo",      False),
    ("fred",       "FRED (Economic Indicators)",         "fetchers.fred",       "fetch_fred",       True),
    ("reliefweb",  "ReliefWeb (Humanitarian)",           "fetchers.reliefweb",  "fetch_reliefweb",  False),
]

KEY_CHECKS = {
    "FIRMS_MAP_KEY":  ("NASA FIRMS key",       "https://firms.modaps.eosdis.nasa.gov/api/"),
    "ACLED_KEY":      ("ACLED key",            "https://acleddata.com/register/"),
    "ACLED_EMAIL":    ("ACLED email",          "https://acleddata.com/register/"),
    "OPENSKY_USER":   ("OpenSky username",     "https://opensky-network.org/  (optional)"),
    "FRED_API_KEY":   ("FRED API key",         "https://fred.stlouisfed.org/docs/api/api_key.html"),
}


def test_source(key, label, module_path, func_name, needs_key):
    import importlib
    t0 = time.time()
    try:
        mod  = importlib.import_module(module_path)
        fn   = getattr(mod, func_name)
        data = fn()
        elapsed = round(time.time() - t0, 1)

        if data.get("error"):
            warn(f"{label}  [{elapsed}s]  ⚠ {data['error'][:60]}")
            return False
        if data.get("note"):
            n = _count(data)
            warn(f"{label}  [{elapsed}s]  ⚠ {data['note'][:60]}")
            return True

        n = _count(data)
        ok(f"{label}  [{elapsed}s]  {n} records")
        return True
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        err(f"{label}  [{elapsed}s]  {type(e).__name__}: {str(e)[:70]}")
        return False


def main():
    print()
    print(f"{BOLD}{'═'*60}{RST}")
    print(f"{BOLD}  SENTINEL Diagnostics{RST}")
    print(f"{'═'*60}")
    print()

    # ── API key status ─────────────────────────────────────────
    print(f"{BOLD}  API Key Configuration{RST}")
    print(f"  {'─'*50}")
    any_missing = False
    for env_var, (label, url) in KEY_CHECKS.items():
        val = os.environ.get(env_var, "")
        if val:
            masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
            ok(f"{label:30s}  {DIM}{masked}{RST}")
        else:
            warn(f"{label:30s}  {DIM}not set — {url}{RST}")
            any_missing = True
    print()

    # ── Source connectivity tests ──────────────────────────────
    print(f"{BOLD}  Source Connectivity{RST}  {DIM}(running in parallel, may take 15–30s){RST}")
    print(f"  {'─'*50}")

    results   = {}
    threads   = []
    lock      = threading.Lock()

    def run_test(args):
        key, label, mod, fn, needs_key = args
        success = test_source(key, label, mod, fn, needs_key)
        with lock:
            results[key] = success

    for args in TESTS:
        t = threading.Thread(target=run_test, args=(args,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=35)

    # ── Summary ────────────────────────────────────────────────
    n_ok  = sum(1 for v in results.values() if v)
    n_err = len(results) - n_ok
    print()
    print(f"{'═'*60}")
    if n_err == 0:
        print(f"  {GRN}{BOLD}All {n_ok} sources OK — ready to run!{RST}")
    else:
        print(f"  {YLW}{BOLD}{n_ok}/{len(results)} sources OK  ·  {n_err} with issues{RST}")
        print(f"  {DIM}Sources with errors will use fallbacks or be skipped.{RST}")
        print(f"  {DIM}The dashboard still works with partial data.{RST}")

    if any_missing:
        print()
        print(f"  {DIM}Add API keys to .env for fuller data coverage.{RST}")
        print(f"  {DIM}See README.md for registration links.{RST}")

    print(f"{'═'*60}")
    print()
    print(f"  To launch:  {CYN}python3 run.py{RST}")
    print(f"  Dashboard:  {CYN}http://localhost:{os.environ.get('PORT', 5117)}{RST}")
    print()


if __name__ == "__main__":
    main()
