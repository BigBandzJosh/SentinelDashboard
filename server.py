"""
OSINT Terminal — Personal Intelligence Dashboard
Main server: Flask + SSE, background sweep engine, data cache
"""

import os, json, time, threading, queue, logging
from datetime import datetime, timezone
from flask import Flask, Response, send_from_directory, jsonify, request

# ── Fetcher imports ────────────────────────────────────────────────────────────
from fetchers.rss        import fetch_rss
from fetchers.firms      import fetch_firms
from fetchers.opensky    import fetch_opensky
from fetchers.acled      import fetch_acled
from fetchers.safecast   import fetch_safecast
from fetchers.celestrak  import fetch_celestrak
from fetchers.yahoo      import fetch_yahoo
from fetchers.fred       import fetch_fred
from fetchers.reliefweb  import fetch_reliefweb

# ── Config ─────────────────────────────────────────────────────────────────────
SWEEP_INTERVAL = int(os.environ.get("SWEEP_INTERVAL", 900))   # seconds (15 min)
PORT            = int(os.environ.get("PORT", 5117))
DEBUG           = os.environ.get("DEBUG", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("osint")

app = Flask(__name__, static_folder=".")

# ── State ──────────────────────────────────────────────────────────────────────
_cache: dict       = {}          # latest sweep data
_prev_cache: dict  = {}          # previous sweep for delta
_sweep_lock        = threading.Lock()
_sse_clients: list = []          # list of queue.Queue
_sse_lock          = threading.Lock()
_sweep_count       = 0
_last_sweep_ts     = None

# ── SSE broadcast ──────────────────────────────────────────────────────────────

def broadcast(event: str, data: dict):
    """Push an SSE event to all connected clients."""
    payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    dead = []
    with _sse_lock:
        for q in _sse_clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# ── Sweep engine ───────────────────────────────────────────────────────────────

FETCHERS = {
    "rss":       (fetch_rss,       "World News (RSS Feeds)"),
    "firms":     (fetch_firms,     "Satellite Fire Detection (NASA FIRMS)"),
    "opensky":   (fetch_opensky,   "Live Flight Tracking (OpenSky)"),
    "acled":     (fetch_acled,     "Armed Conflict Events (ACLED)"),
    "safecast":  (fetch_safecast,  "Radiation Monitoring (Safecast)"),
    "celestrak": (fetch_celestrak, "Satellite Tracking (CelesTrak)"),
    "yahoo":     (fetch_yahoo,     "Live Markets (Yahoo Finance)"),
    "fred":      (fetch_fred,      "Economic Indicators (FRED)"),
    "reliefweb": (fetch_reliefweb, "Humanitarian Alerts (ReliefWeb)"),
}


def run_sweep():
    global _cache, _prev_cache, _sweep_count, _last_sweep_ts

    log.info("═" * 60)
    log.info("  SWEEP STARTING")
    log.info("═" * 60)

    new_data   = {}
    source_health = {}
    start_ts   = time.time()

    threads = []
    results = {}

    def _run(key, fn):
        try:
            results[key] = fn()
            source_health[key] = {"status": "ok", "count": _count(results[key])}
            log.info(f"  ✓  {key:12s}  {source_health[key]['count']} records")
        except Exception as e:
            results[key]       = {}
            source_health[key] = {"status": "error", "error": str(e)}
            log.warning(f"  ✗  {key:12s}  {e}")

    for key, (fn, _) in FETCHERS.items():
        t = threading.Thread(target=_run, args=(key, fn), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=30)

    new_data = results
    new_data["_meta"] = {
        "sweep_count":      _sweep_count + 1,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "duration_s":       round(time.time() - start_ts, 1),
        "sweep_interval_s": SWEEP_INTERVAL,
        "source_health":    source_health,
    }

    # Compute delta
    delta = _compute_delta(_cache, new_data)
    new_data["_delta"] = delta

    with _sweep_lock:
        _prev_cache  = _cache.copy()
        _cache       = new_data
        _sweep_count += 1
        _last_sweep_ts = new_data["_meta"]["timestamp"]

    elapsed = round(time.time() - start_ts, 1)
    log.info(f"  Sweep #{_sweep_count} complete in {elapsed}s")
    log.info("═" * 60)

    broadcast("sweep", new_data)
    return new_data


def _count(data):
    if isinstance(data, list):   return len(data)
    if isinstance(data, dict):
        for k in ("events","fires","flights","conflicts","readings","satellites","alerts","indicators"):
            if k in data and isinstance(data[k], list):
                return len(data[k])
        # Yahoo Finance: markets is a dict of category lists
        if "markets" in data and isinstance(data["markets"], dict):
            return sum(len(v) for v in data["markets"].values() if isinstance(v, list))
    return 0


def _compute_delta(old: dict, new: dict) -> dict:
    """Very simple delta: count changes per source."""
    delta = {}
    for key in FETCHERS:
        old_c = _count(old.get(key, {}))
        new_c = _count(new.get(key, {}))
        delta[key] = {"prev": old_c, "now": new_c, "change": new_c - old_c}
    return delta


def _sweep_loop():
    """Background thread: sweep immediately, then every SWEEP_INTERVAL seconds."""
    run_sweep()
    while True:
        time.sleep(SWEEP_INTERVAL)
        run_sweep()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "dashboard.html")


@app.route("/api/data")
def api_data():
    with _sweep_lock:
        return jsonify(_cache)


@app.route("/api/sweep", methods=["POST"])
def api_sweep():
    """Force an immediate sweep (for manual refresh)."""
    t = threading.Thread(target=run_sweep, daemon=True)
    t.start()
    return jsonify({"status": "sweep started"})


@app.route("/api/aoi", methods=["GET"])
def api_aoi_get():
    bbox = os.environ.get("FIRMS_BBOX", "")
    return jsonify({"bbox": bbox if bbox else None})


@app.route("/api/aoi", methods=["POST"])
def api_aoi_set():
    """Set AOI bounding box from drawn rectangle. Expects {bbox: "west,south,east,north"}."""
    data = request.get_json(force=True)
    bbox = data.get("bbox", "")
    parts = bbox.split(",")
    if len(parts) != 4:
        return jsonify({"error": "bbox must be west,south,east,north"}), 400
    try:
        [float(p) for p in parts]
    except ValueError:
        return jsonify({"error": "bbox values must be numeric"}), 400
    os.environ["FIRMS_BBOX"] = bbox
    log.info(f"  AOI set → {bbox}")
    return jsonify({"bbox": bbox, "status": "ok"})


@app.route("/api/aoi", methods=["DELETE"])
def api_aoi_clear():
    os.environ["FIRMS_BBOX"] = ""
    log.info("  AOI cleared → global")
    return jsonify({"bbox": None, "status": "ok"})


@app.route("/api/status")
def api_status():
    with _sweep_lock:
        return jsonify({
            "sweep_count":  _sweep_count,
            "last_sweep":   _last_sweep_ts,
            "interval_s":   SWEEP_INTERVAL,
            "sources":      list(FETCHERS.keys()),
        })


@app.route("/stream")
def stream():
    """SSE endpoint — clients subscribe here for live push updates."""
    q = queue.Queue(maxsize=5)
    with _sse_lock:
        _sse_clients.append(q)

    def generate():
        # Send current cache immediately on connect
        with _sweep_lock:
            snapshot = _cache.copy()
        if snapshot:
            yield f"event: sweep\ndata: {json.dumps(snapshot)}\n\n"

        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": heartbeat\n\n"   # keep-alive ping
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering":"no",
            "Connection":       "keep-alive",
        },
    )


# ── Entry point ────────────────────────────────────────────────────────────────
# Use run.py to start the server. It loads .env and starts the sweep thread
# before calling app.run(). Do not run server.py directly.
