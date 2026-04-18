# SENTINEL — Personal Intelligence Terminal

A self-hosted OSINT dashboard that aggregates 9 real-time public data feeds into a
single flat-map interface. Runs locally on your machine. No cloud, no telemetry,
no subscriptions.

```
Built entirely from public/open data sources.
For personal research use only.
```

---

## What it shows

| Panel | Source | Key Required |
|---|---|---|
| Conflict events (map + list) | ACLED | Free researcher key (or static fallback) |
| Satellite fire detection | NASA FIRMS | Free key (or reduced fallback) |
| Live flight tracking | OpenSky Network | No (optional account for higher limits) |
| Radiation monitoring | Safecast | No |
| Geopolitical news events | GDELT 2.0 | No |
| Satellite constellation tracking | CelesTrak | No |
| Live markets (indices/crypto/energy/FX) | Yahoo Finance | No |
| Economic indicators | FRED (US Fed) | Free instant key |
| Humanitarian alerts & situation reports | ReliefWeb (UN) | No |

---

## Setup

### 1. Clone / copy this folder to your machine

```bash
# If you have it as a zip, just extract it anywhere convenient
# e.g. ~/sentinel/
```

### 2. Install Python dependencies

Python 3.9+ required. Only two non-stdlib packages needed:

```bash
pip install flask requests
```

### 3. Configure API keys (optional but recommended)

```bash
cp .env.example .env
# Open .env in any text editor and fill in your keys
```

**Free keys worth getting (takes 2 minutes each):**

- **FRED** → https://fred.stlouisfed.org/docs/api/api_key.html
  Unlocks the economic indicators panel (Fed Funds Rate, CPI, unemployment, yield spread, etc.)

- **NASA FIRMS** → https://firms.modaps.eosdis.nasa.gov/api/
  Higher-resolution VIIRS fire data. Works without it but with reduced coverage.

- **ACLED** → https://acleddata.com/register/
  Live armed conflict events. Without it, a static fallback of known conflict zones is used.

- **OpenSky** (optional) → https://opensky-network.org/
  Create a free account to avoid rate limiting on flight data.

### 4. Run

```bash
python3 run.py
```

Then open your browser to: **http://localhost:5117**

The first sweep takes 20–40 seconds to query all sources in parallel.
The dashboard populates automatically when the sweep completes.
After that, it re-sweeps every 15 minutes automatically.

---

## Project Structure

```
sentinel/
├── run.py              ← Start here. Loads .env and launches server.
├── server.py           ← Flask server, SSE engine, sweep orchestrator
├── dashboard.html      ← Entire frontend (single file, no build step)
├── .env                ← Your API keys (create from .env.example)
├── .env.example        ← Template with all available options
└── fetchers/
    ├── gdelt.py        ← GDELT 2.0 geopolitical event data
    ├── firms.py        ← NASA FIRMS satellite fire detection
    ├── opensky.py      ← OpenSky live flight tracking
    ├── acled.py        ← ACLED armed conflict events
    ├── safecast.py     ← Safecast citizen radiation monitoring
    ├── celestrak.py    ← CelesTrak satellite constellation tracking
    ├── yahoo.py        ← Yahoo Finance live market data
    ├── fred.py         ← FRED US economic indicators
    └── reliefweb.py    ← ReliefWeb UN humanitarian alerts
```

---

## Configuration

All options live in `.env`:

```bash
PORT=5117              # Dashboard port
SWEEP_INTERVAL=900     # Seconds between sweeps (default 15 min)
DEBUG=false            # Flask debug mode

FIRMS_MAP_KEY=         # NASA FIRMS key
ACLED_KEY=             # ACLED key
ACLED_EMAIL=           # ACLED account email
OPENSKY_USER=          # OpenSky username (optional)
OPENSKY_PASS=          # OpenSky password (optional)
FRED_API_KEY=          # FRED key
```

---

## Dashboard controls

| Control | Action |
|---|---|
| Layer buttons (top-right of map) | Toggle each data layer on/off |
| ⟳ SWEEP button (top-right header) | Force an immediate sweep |
| Panel headers | Click to collapse/expand any panel |
| Map markers | Click for detail popup |
| Scroll on map | Zoom in/out |
| Drag map | Pan |

---

## How sweeps work

Every 15 minutes (configurable), the server:

1. Queries all 9 sources **in parallel** using threads
2. Computes a **delta** vs. the previous sweep (what changed)
3. Pushes the new data to all connected browsers instantly via **SSE** (Server-Sent Events)
4. The dashboard re-renders all map layers and panels automatically

You never need to refresh the page.

---

## Troubleshooting

**Dashboard shows "Awaiting sweep..." for more than 60 seconds**
→ Check your terminal for error output. One or more fetchers may be timing out.
→ GDELT and OpenSky are the most likely to be slow or throttled.

**OpenSky returns no flights**
→ The public endpoint rate-limits aggressively. Create a free OpenSky account and add credentials to `.env`.

**ACLED shows only static conflict zones**
→ Expected behaviour when no ACLED key is set. Register free at acleddata.com.

**Economic indicators panel is empty**
→ FRED requires a free API key. Takes 30 seconds to get one.

**Map tiles not loading**
→ You need internet access for the CartoDB dark tiles. The data fetchers also need internet.
→ If running fully offline, replace the tile URL in `dashboard.html` with a local tile server.

---

## Extending it

Each fetcher is a standalone Python module with a single `fetch_*()` function that returns a dict.
To add a new source:

1. Create `fetchers/mysource.py` with a `fetch_mysource()` function
2. Add it to the `FETCHERS` dict in `server.py`
3. Add rendering logic in `dashboard.html` (follow the pattern of existing panels)

---

## Data sources & attribution

- **GDELT** — gdeltproject.org — Open, no license restrictions
- **NASA FIRMS** — firms.modaps.eosdis.nasa.gov — US Government open data
- **OpenSky** — opensky-network.org — Creative Commons, research use
- **ACLED** — acleddata.com — Free for non-commercial research with attribution
- **Safecast** — safecast.org — Creative Commons CC0
- **CelesTrak** — celestrak.org — Public domain
- **Yahoo Finance** — Unofficial endpoint, personal use only
- **FRED** — fred.stlouisfed.org — Public domain (US Federal Reserve)
- **ReliefWeb** — reliefweb.int — UN OCHA open data
