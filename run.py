#!/usr/bin/env python3
"""
SENTINEL startup script
Loads .env file then launches the server.
Usage: python3 run.py
"""

import os, sys
from pathlib import Path

def load_env(path=".env"):
    p = Path(path)
    if not p.exists():
        print(f"[SENTINEL] No .env found — using .env.example defaults")
        p = Path(".env.example")
    if not p.exists():
        return

    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        val = val.strip()
        if val and not os.environ.get(key):   # don't overwrite real env vars
            os.environ[key] = val

load_env()

# Now import and run server
from server import app, _sweep_loop, PORT, DEBUG, log
import threading

log.info("=" * 60)
log.info("  SENTINEL Personal Intelligence Terminal")
log.info("=" * 60)
log.info(f"  Dashboard → http://localhost:{PORT}")
log.info(f"  Sweep interval: {os.environ.get('SWEEP_INTERVAL', 900)}s")
log.info("")
log.info("  Data sources:")
log.info("    ✓ RSS News (BBC, AJ, Guardian+)  — no key needed")
log.info("    ✓ NASA FIRMS (fires)            — %s" % ("key set" if os.environ.get("FIRMS_MAP_KEY") else "no key, using fallback"))
log.info("    ✓ OpenSky (flights)             — %s" % ("auth set" if os.environ.get("OPENSKY_USER") else "anonymous (may throttle)"))
log.info("    ✓ ACLED (conflicts)             — %s" % ("key set" if os.environ.get("ACLED_KEY") else "no key, using static fallback"))
log.info("    ✓ Safecast (radiation)          — no key needed")
log.info("    ✓ CelesTrak (satellites)        — no key needed")
log.info("    ✓ Yahoo Finance (markets)       — no key needed")
log.info("    ✓ FRED (economics)              — %s" % ("key set" if os.environ.get("FRED_API_KEY") else "no key — panel will be empty"))
log.info("    ✓ ReliefWeb (humanitarian)      — no key needed")
log.info("=" * 60)

t = threading.Thread(target=_sweep_loop, daemon=True)
t.start()

app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False, threaded=True)
