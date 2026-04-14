# AstroBridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/myrakhandelwal/AstroBridge/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Status: Stable](https://img.shields.io/badge/status-stable-green.svg)](https://github.com/myrakhandelwal/AstroBridge)
[![GitHub](https://img.shields.io/badge/github-myrakhandelwal%2FAstroBridge-blue.svg)](https://github.com/myrakhandelwal/AstroBridge)

**Version: 0.3.3** — Live Catalog Lookup, Multi-Catalog AI Identification, 261 Tests

AstroBridge is an astronomical source matching and cross-catalog identification pipeline. You give it an object name or sky coordinates; it fans out to real catalogs (SIMBAD, NED, Gaia DR3, 2MASS), merges the results, and optionally generates a plain-language description using an LLM.

---

## Install

```bash
git clone https://github.com/myrakhandelwal/AstroBridge.git
cd AstroBridge
python -m venv .venv && source .venv/bin/activate

pip install -e .[dev]        # core + tests
pip install -e .[live]       # + Gaia DR3, 2MASS, SIMBAD/NED live TAP
pip install -e .[web]        # + FastAPI web console
pip install anthropic         # + Claude AI descriptions (optional)
pip install openai            # + OpenAI/local-compatible AI descriptions (optional)
```

---

## Quick Start

```bash
# End-to-end pipeline demo (synthetic data, no network needed)
python demo.py

# Identify an object and get catalog recommendations
astrobridge-identify "Proxima Centauri"
astrobridge-identify "Find nearby red dwarf stars"

# Interactive menu-driven demo
python interactive_demo.py

# Web console at http://127.0.0.1:8000
astrobridge-web
```

---

## Live Catalog Lookup

`lookup_object()` uses a two-step strategy — no local database required:

1. **Name resolution** — fans out to SIMBAD + NED concurrently
2. **Positional enrichment** — uses the returned coordinates to cone-search Gaia DR3 and 2MASS

```python
import asyncio
from astrobridge.lookup import lookup_object, lookup_by_coordinates

async def main():
    # Look up by name
    obj = await lookup_object("Proxima Centauri")
    if obj:
        print(obj.primary_name)          # Proxima Centauri
        print(f"RA={obj.ra:.4f}  Dec={obj.dec:.4f}")
        print("catalogs:", list(obj.catalog_entries.keys()))
        print("photometry:", obj.photometry_summary)

    # Cone search by coordinates
    results = await lookup_by_coordinates(ra=217.429, dec=-62.680, radius_arcsec=60)
    for r in results:
        print(r.primary_name, r.ra, r.dec)

asyncio.run(main())
```

**Requires** `pip install -e .[live]` for live network queries. Falls back to local connectors automatically when `pyvo` is not installed.

---

## Object Identification

Combines NLP routing, live catalog lookup, and optional AI description in one call:

```python
import asyncio
from astrobridge.identify import identify_from_catalogs

async def main():
    result = await identify_from_catalogs("M31")
    print(result["object_class"])       # galaxy
    print(result["description"])        # plain-language description
    print(result["top_catalogs"])       # ['NED', 'SDSS', 'ALLWISE']
    print(result["catalog_data"])       # real RA/Dec + photometry from catalogs

asyncio.run(main())
```

For CLI use:

```bash
astrobridge-identify "M31"
astrobridge-identify "Find high-redshift quasars"
astrobridge-identify --json "Betelgeuse"
```

---

## AI Descriptions

Set environment variables to enable real LLM descriptions. Defaults to a deterministic stub (no API key needed).

```bash
# Anthropic Claude (recommended)
export AI_PROVIDER=anthropic
export AI_API_KEY=sk-ant-...

# OpenAI
export AI_PROVIDER=openai
export AI_API_KEY=sk-...
export AI_MODEL=gpt-4o-mini

# Local OpenAI-compatible endpoint (example)
export AI_PROVIDER=local
export AI_BASE_URL=http://127.0.0.1:11434/v1
export AI_MODEL=your-local-model

# Stub (default — no key needed)
export AI_PROVIDER=stub
```

Configuration is considered "real AI" when the provider requirements are satisfied:

- `openai` or `anthropic`: set `AI_API_KEY`
- `local`: set `AI_BASE_URL`
- `stub`: deterministic offline fallback

```python
from astrobridge.ai_description import generate_description
from astrobridge.models import UnifiedObject

obj = UnifiedObject(primary_name="M31", ra=10.685, dec=41.269, object_type="galaxy")
print(generate_description(obj))
```

---

## Bayesian Cross-Matching

```python
from astrobridge.matching import BayesianMatcher

matcher = BayesianMatcher(proper_motion_aware=True)
matches = matcher.match(reference_sources, candidate_sources)

for m in matches:
    print(f"{m.source1_id} ↔ {m.source2_id}  p={m.match_probability:.3f}  sep={m.separation_arcsec:.2f}\"")
```

Matching controls available on every `QueryRequest`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `proper_motion_aware` | bool | Apply proper-motion corrections across epochs |
| `match_epoch` | datetime | Reference epoch for PM corrections |
| `weighting_profile` | str | `balanced` \| `position_first` \| `photometry_first` |
| `astrometric_weight` | 0–1 | Manual astrometric weight override |
| `photometric_weight` | 0–1 | Manual photometric weight override |

---

## Orchestrator (Multi-Catalog Queries)

```python
import asyncio
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.matching import BayesianMatcher
from astrobridge.routing import NLPQueryRouter

async def main():
    orch = AstroBridgeOrchestrator(router=NLPQueryRouter(), matcher=BayesianMatcher())

    # Name query
    req = QueryRequest(query_type="name", name="Sirius", auto_route=True)
    resp = await orch.execute_query(req)
    print(resp.status, len(resp.sources), "sources")

    # Natural language
    req2 = QueryRequest(
        query_type="natural_language",
        description="Find nearby infrared-bright red dwarfs",
        auto_route=True,
        weighting_profile="position_first",
    )
    resp2 = await orch.execute_query(req2)
    print(resp2.routing_reasoning)

asyncio.run(main())
```

---

## Supported Catalogs

| Catalog | Live Adapter | Name Lookup | Cone Search | Best For |
|---------|-------------|-------------|-------------|----------|
| SIMBAD | `SimbadTapAdapter` | ✅ | ✅ | All objects, name resolution |
| NED | `NedTapAdapter` | ✅ | ✅ | Galaxies, AGN, quasars |
| Gaia DR3 | `GaiaDR3TapAdapter` | — | ✅ | Stars: astrometry + proper motions |
| 2MASS | `TwoMassTapAdapter` | — | ✅ | Stars + galaxies: J/H/Ks photometry |
| SDSS | routing only | | | Galaxies, QSOs, optical photometry |
| WISE | routing only | | | Mid-IR sources, AGN |
| AllWISE | routing only | | | Improved WISE + proper motions |
| PanSTARRS | routing only | | | Transients, wide-field optical |
| ZTF | routing only | | | Supernovae, variables, transients |
| ATLAS | routing only | | | Transient alerts, SNe |
| Hipparcos | routing only | | | Bright stars (V < 12) |
| VizieR | routing only | | | Any published catalog table |
| NASA Exoplanet Archive | routing only | | | Exoplanet host stars |

Live adapters require `pip install -e .[live]`.

---

## Web Console

```bash
pip install -e .[web]
astrobridge-web
# → http://127.0.0.1:8000
```

REST API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query` | Run a cross-catalog query |
| `POST` | `/api/identify` | Identify object + live catalog lookup + AI description |
| `POST` | `/api/jobs` | Submit async background job |
| `GET` | `/api/jobs/{id}` | Check job status |
| `GET` | `/api/jobs/{id}/result` | Fetch completed job result |
| `POST` | `/api/analytics/event` | Record analytics event |
| `GET` | `/api/analytics/summary` | Aggregate analytics summary |
| `POST` | `/api/benchmark/run` | Run latency benchmark |

---

## Quality Gates

```bash
ruff check .          # linting
mypy astrobridge/     # strict type checking on core modules
pytest -q             # 261 tests, zero warnings
```

All gates run automatically on every push via GitHub Actions.

---

## Persistent State

Jobs and analytics are persisted in SQLite. Default path: `.astrobridge/state.db`

```bash
export ASTROBRIDGE_STATE_DB="/path/to/state.db"   # override location
```

---

## Package API Reference

| Import | Description |
|--------|-------------|
| `astrobridge.lookup.lookup_object` | Two-step live catalog fan-out by name |
| `astrobridge.lookup.lookup_by_coordinates` | Concurrent cone search across all live adapters |
| `astrobridge.identify.identify_from_catalogs` | NLP routing + live lookup + AI description |
| `astrobridge.identify.identify_object` | NLP classification only (no network) |
| `astrobridge.api.AstroBridgeOrchestrator` | Multi-catalog query orchestration |
| `astrobridge.api.QueryRequest` | Request model with matcher + routing controls |
| `astrobridge.matching.BayesianMatcher` | Probabilistic cross-matching with PM support |
| `astrobridge.matching.ConfidenceScorer` | Match confidence with weighting profiles |
| `astrobridge.connectors.SimbadTapAdapter` | Live SIMBAD TAP (name + cone) |
| `astrobridge.connectors.NedTapAdapter` | Live NED TAP (name + cone) |
| `astrobridge.connectors.GaiaDR3TapAdapter` | Live Gaia DR3 TAP (cone only) |
| `astrobridge.connectors.TwoMassTapAdapter` | Live 2MASS TAP via IRSA (cone only) |
| `astrobridge.ai_description.generate_description` | LLM description (anthropic / openai / stub) |
| `astrobridge.analytics.AnalyticsStore` | SQLite-backed telemetry events |
| `astrobridge.jobs.JobManager` | Background job lifecycle manager |
| `astrobridge.benchmarking.BenchmarkRunner` | Reproducible latency benchmarks |
| `astrobridge.database` | SQLite persistence for objects, sources, calibration frames |
| `astrobridge.ccd_calibration.calibrate_ccd` | CCD reduction: bias/dark/flat (astropy or NumPy) |
| `astrobridge.models.UnifiedObject` | Merged multi-catalog view with `from_sources()` |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/Command Guide.md](docs/Command%20Guide.md) | CLI commands, REST API, Python API examples |
| [docs/Algorithm and Science.md](docs/Algorithm%20and%20Science.md) | Bayesian matching math, proper-motion corrections |
| [docs/Architecture Guide.md](docs/Architecture%20Guide.md) | System design, component flow, custom adapters |
| [docs/Deployment Guide.md](docs/Deployment%20Guide.md) | Docker, AWS, PyPI release, monitoring |
| [docs/Platforms_and_Catalogs_Matrix.md](docs/Platforms_and_Catalogs_Matrix.md) | All 13 catalogs: routing scores, adapter status |
| [docs/Test Suite Guide.md](docs/Test%20Suite%20Guide.md) | All 261 tests described by file and category |
| [docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md) | Full changelog: v0.1.1 → v0.3.3 |

---

## Project Layout

```
astrobridge/
├── models.py           # Source, Coordinate, UnifiedObject, MatchResult
├── lookup.py           # Live two-step catalog fan-out
├── identify.py         # NLP classification + identify_from_catalogs()
├── connectors.py       # SimbadTapAdapter, NedTapAdapter, GaiaDR3TapAdapter, TwoMassTapAdapter
├── ai_description.py   # LLM descriptions (anthropic / openai / stub)
├── database.py         # SQLite persistence layer
├── ccd_calibration.py  # CCD reduction pipeline
├── geometry.py         # Angular distance calculations
├── routing/            # NLPQueryRouter, CatalogRanker, 13 CatalogTypes
├── matching/           # BayesianMatcher, ConfidenceScorer, SpatialIndex
├── api/                # AstroBridgeOrchestrator, QueryRequest/Response
├── web/                # FastAPI app, REST endpoints, HTML console
├── analytics.py        # AnalyticsStore, event tracking
├── jobs.py             # JobManager, background query lifecycle
└── benchmarking.py     # BenchmarkRunner
```

---

## Release History

| Tag | Date | Highlights |
|-----|------|------------|
| `v0.3.3` | Apr 14 2026 | Live catalogs, Gaia DR3 + 2MASS adapters, AI descriptions, 261 tests |
| `v0.3.2` | Apr 9 2026 | mypy strict fixes |
| `v0.3.1` | Apr 9 2026 | Interactive demo, test suite guide |
| `v0.3.0` | Apr 9 2026 | PEP 621 packaging, ruff, async concurrency |
| `v0.2.0` | Apr 8 2026 | Comprehensive docs, deployment guide |
| `v0.1.1` | — | Initial release |

---

## License

MIT License — Copyright © 2026 Myra Khandelwal

Simbad and NED fall back to local deterministic datasets when `pyvo` is not installed, so all tests and demos run without network access.
