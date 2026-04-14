# AstroBridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/myrakhandelwal/AstroBridge/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Status: Stable](https://img.shields.io/badge/status-stable-green.svg)](https://github.com/myrakhandelwal/AstroBridge)
[![GitHub](https://img.shields.io/badge/github-myrakhandelwal%2FAstroBridge-blue.svg)](https://github.com/myrakhandelwal/AstroBridge)

**Version: 0.3.0** — Modern Python Packaging, Strict Type Safety, Production-Ready

AstroBridge is a compact astronomical source matching pipeline that combines three pieces:

* type-safe source models for catalogs and coordinates
* intelligent query routing for catalog selection
* Bayesian cross-matching for candidate association  

The repository also includes async orchestration with bounded network concurrency, comprehensive quality gates, and a runnable demo for new users.

Recent additions include confidence scoring for every match, optional proper-motion-aware epoch matching, and modern PEP 621 packaging with setuptools_scm automation.

## Quick Start

Create a virtual environment, install the package, then run CLI-first workflows.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Run the demo:

```bash
astrobridge-demo
```

Or run it directly:

```bash
python demo.py
```

Run the test suite:

```bash
pytest
```

Run the object-identification command:

```bash
astrobridge-identify "Find nearby red dwarf stars"
```

This prints the inferred object class, a short description of what it is, the suggested search radius, and the best starting catalogs.

## Interactive Live Demo

For hands-on exploration with live user input, run the interactive demo:

```bash
python interactive_demo.py
```

Or via entry point:

```bash
astrobridge-interactive
```

The interactive demo provides a menu-driven interface to:
- **Query by object name** — Search for specific astronomical objects (Proxima Centauri, M31, etc.)
- **Query by coordinates** — Cone search around RA/Dec position with custom radius
- **Natural language queries** — Describe what you're looking for; router handles the rest
- **Object identification** — Classify targets and get recommended catalogs
- **Advanced matcher controls** — Test different confidence weighting profiles
- **Performance benchmarking** — Measure query latency across iterations

All queries use live connectors (if `[live]` is installed) or fall back to local synthetic data for teaching/testing.

## Quality Gates & Type Safety

**All checks passing** ✅

```bash
# Modern linting with Ruff
ruff check .          # E, F, I, UP, B, SIM rules

# Strict type checking on core modules  
mypy astrobridge/     # Protocol-based typing, null safety

# Complete test coverage
pytest -q             # 261 tests passing, zero warnings
```

**Automated Versioning**  
Versions are automatically derived from git tags using `setuptools_scm`. No manual version edits needed.

```bash
# To release a new version
git tag -a v0.3.1 -m "Release message"
git push --tags
# Version auto-bumps at build time
```

## Optional Web UI

The web console is an optional side interface for interactive use. The primary workflow remains CLI and importable Python modules.

```bash
pip install -e .[web]
./.venv/bin/astrobridge-web
```

Then open `http://127.0.0.1:8000` in your browser.

## Command Reference

Commands currently developed in AstroBridge:

1. `astrobridge-demo`
	Runs the end-to-end demonstration of models, routing, matching, and orchestration.

2. `python demo.py`
	Alternate way to run the same demo script directly.

3. `astrobridge-identify "<input>"`
	Classifies the object/query text and returns a plain-language description, recommended search radius, and top catalogs.

4. `python -m astrobridge.identify "<input>"`
	Module-invocation fallback for identification (useful if console scripts are not on PATH).

5. `astrobridge-web`
	Starts the FastAPI web console on `127.0.0.1:8000` (optional UI path).

6. `python -m astrobridge.web.app`
	Module-invocation fallback to start the same web server.

7. `pytest`
	Runs the full test suite.

8. `pytest tests/test_identify.py tests/test_web.py -q`
	Fast validation for identification and web error-handling paths.

9. `pip install -e .[dev]`
	Installs AstroBridge in editable mode with development dependencies.

10. `pip install -e .[live]`
	 Installs optional live TAP adapter dependencies.

11. `pip install -e .[web]`
	 Installs optional web console dependencies.

## Advanced API Endpoints

The following production-foundation endpoints are now available in the FastAPI app:

1. `POST /api/jobs`
	Submit an asynchronous query job for longer-running workloads.

2. `GET /api/jobs/{job_id}`
	Check background job status (`queued`, `running`, `completed`, `failed`).

3. `GET /api/jobs/{job_id}/result`
	Fetch completed job output.

4. `POST /api/analytics/event`
	Record educational or operational analytics events.

5. `GET /api/analytics/summary`
	Return aggregate analytics summary for tracked events.

6. `POST /api/benchmark/run`
	Execute a reproducible benchmark run and return latency/success metrics.

## Persistent State (Jobs + Analytics)

AstroBridge now persists background job records and analytics events in SQLite.

By default, state is stored at:

```text
.astrobridge/state.db
```

Override location with:

```bash
export ASTROBRIDGE_STATE_DB="/absolute/path/to/state.db"
```

This persistence is used by:

1. `POST /api/jobs` and related job result/status endpoints.
2. `POST /api/analytics/event` and `GET /api/analytics/summary`.

## Documentation

For detailed information:

1. **[docs/Command Guide.md](docs/Command%20Guide.md)** — Complete user guide with CLI commands, REST API endpoints, Python API examples, and expected output samples.

2. **[docs/Algorithm and Science.md](docs/Algorithm%20and%20Science.md)** — Deep dive into the Bayesian matching algorithm, mathematical foundations, photometric and astrometric likelihoods, proper-motion corrections, and practical examples with real data.

3. **[docs/Architecture Guide.md](docs/Architecture%20Guide.md)** — System architecture, component design, advanced usage patterns, custom catalog adapters, batch processing, reproducible workflows, and teaching applications for research and education.

4. **[docs/Deployment Guide.md](docs/Deployment%20Guide.md)** — Production deployment strategies (Docker, AWS, Kubernetes), PyPI releases, database setup, monitoring, security hardening, and disaster recovery planning.

5. **[docs/AstroBridge_Research_Paper_Full.tex](docs/AstroBridge_Research_Paper_Full.tex)** — Full research manuscript aligned with the implemented pipeline, including validated benchmark and test metrics.

6. **[docs/AstroBridge_Research_Paper_Conference.tex](docs/AstroBridge_Research_Paper_Conference.tex)** — Short conference-format paper version (4-6 pages) for submissions.

7. **[docs/Platforms_and_Catalogs_Matrix.md](docs/Platforms_and_Catalogs_Matrix.md)** — Catalog and platform matrix showing object coverage and recommended usage.

## Package API Reference (Current)

Key public classes/functions currently implemented:

1. `astrobridge.api.AstroBridgeOrchestrator`
	Main orchestration entry for routed catalog querying.

2. `astrobridge.api.QueryRequest`
	Request model including routing and matcher controls.

3. `astrobridge.matching.BayesianMatcher`
	Probabilistic matcher with proper-motion-aware options.

4. `astrobridge.matching.ConfidenceScorer`
	Match confidence computation with weighting profiles.

5. `astrobridge.identify.identify_object`
	AI-assisted classification and explanatory target description.

6. `astrobridge.analytics.AnalyticsStore`
	Event store with SQLite-backed telemetry persistence.

7. `astrobridge.jobs.JobManager`
	Background query job lifecycle manager with persisted state.

8. `astrobridge.benchmarking.BenchmarkRunner`
	Reproducible latency/success benchmark execution.

9. `astrobridge.database`
	SQLite persistence layer: `objects`, `catalog_sources`, and `calibration_frames` tables with full CRUD helpers.

10. `astrobridge.ccd_calibration.calibrate_ccd`
	CCD image reduction pipeline (bias, dark, flat); uses `astropy` + `ccdproc` when available, falls back to pure NumPy.

11. `astrobridge.ai_description.generate_description`
	LLM-backed plain-language object descriptions with SQLite caching.  Defaults to a deterministic stub; set `AI_PROVIDER=anthropic` (or `openai`) and `AI_API_KEY` to enable live descriptions.

12. `astrobridge.lookup.lookup_object`
	Two-step live catalog fan-out: SIMBAD/NED resolve the name, then Gaia DR3 + 2MASS enrich with astrometry and multi-band photometry.  No local database required.

13. `astrobridge.connectors.GaiaDR3TapAdapter`
	Live Gaia DR3 cone-search adapter via ESA TAP.  Returns G/BP/RP photometry and proper motions.

14. `astrobridge.connectors.TwoMassTapAdapter`
	Live 2MASS Point Source Catalog adapter via NASA IRSA TAP.  Returns J/H/Ks photometry.

## What You Get

* [astrobridge.models](astrobridge/models.py) — `Source`, `Coordinate`, `Uncertainty`, `Photometry`, `Provenance`, `UnifiedObject`
* [astrobridge.routing](astrobridge/routing) — NLP query routing across 13 catalog types
* [astrobridge.matching](astrobridge/matching) — Bayesian probabilistic source matching
* [astrobridge.api](astrobridge/api) — orchestration, request/response schemas
* [astrobridge.lookup](astrobridge/lookup.py) — live two-step catalog fan-out (no database required)
* [astrobridge.connectors](astrobridge/connectors.py) — live TAP adapters: SIMBAD, NED, Gaia DR3, 2MASS
* [astrobridge.database](astrobridge/database.py) — SQLite-backed persistence (objects, catalog sources, calibration frames)
* [astrobridge.ccd_calibration](astrobridge/ccd_calibration.py) — CCD image reduction (bias/dark/flat)
* [astrobridge.ai_description](astrobridge/ai_description.py) — LLM-generated descriptions (`anthropic` | `openai` | `stub`)

## Supported Catalogs

| Catalog | Type | Live adapter | Object types |
|---------|------|-------------|--------------|
| SIMBAD | General | `SimbadTapAdapter` | All |
| NED | Extragalactic | `NedTapAdapter` | Galaxies, QSOs, AGN |
| Gaia DR3 | Astrometry | `GaiaDR3TapAdapter` | Stars, clusters |
| 2MASS | Near-IR | `TwoMassTapAdapter` | Stars, galaxies |
| SDSS | Optical | routing only | Stars, galaxies, QSOs |
| PanSTARRS | Optical | routing only | Stars, SNe, galaxies |
| WISE | Mid-IR | routing only | All |
| AllWISE | Mid-IR | routing only | AGN, galaxies |
| ZTF | Time-domain | routing only | Transients, SNe, variables |
| ATLAS | Time-domain | routing only | SNe, variables |
| Hipparcos | Astrometry | routing only | Bright stars |
| VizieR | General | routing only | All |
| NASA Exoplanet Archive | Exoplanets | routing only | Exoplanet hosts |

## Matching Features

The probabilistic matcher now supports:

* confidence scoring with human-readable rationale (astrometric, photometric, and ambiguity-aware)
* optional proper-motion-aware matching across catalogs observed at different epochs
* deterministic scoring behavior for reproducible runs and testing

Example usage with proper motion support:

```python
from astrobridge.matching import BayesianMatcher

matcher = BayesianMatcher(proper_motion_aware=True)
matches = matcher.match(ref_sources, candidate_sources)
```

API-level matcher controls are also available through `QueryRequest`:

* `proper_motion_aware` (bool)
* `match_epoch` (datetime)
* `astrometric_weight` (0-1)
* `photometric_weight` (0-1)
* `weighting_profile` (`balanced`, `position_first`, `photometry_first`)

These are applied by the orchestrator before query execution so callers can tune matching behavior per request.

The web console includes these controls directly in the UI so users can run interactive experiments without writing Python code.

## Demo Flow

The demo script walks through the core phases in order and now covers the full package surface:

1. canonical models
2. intelligent routing
3. Bayesian matching
4. async orchestration
5. object identification
6. telemetry, persistence, and background jobs
7. reproducible benchmarking

It uses synthetic data so it can run without external catalog access.

## Development Notes

The test suite uses `pytest-asyncio`, which is included in the `dev` extra.

## License

AstroBridge is licensed under the MIT License. See [LICENSE](LICENSE).

Simbad and NED currently use deterministic local datasets for fast, reliable development and CI validation.

## Live Catalog Adapters

AstroBridge includes live TAP adapters for four catalogs.  All require `pyvo` (install with `pip install -e .[live]`).

| Adapter | Catalog | Name lookup | Cone search | TAP endpoint |
|---------|---------|-------------|-------------|--------------|
| `SimbadTapAdapter` | CDS SIMBAD | ✅ | ✅ | `simbad.cds.unistra.fr` |
| `NedTapAdapter` | NASA NED | ✅ | ✅ | `ned.ipac.caltech.edu` |
| `GaiaDR3TapAdapter` | ESA Gaia DR3 | — | ✅ | `gea.esac.esa.int` |
| `TwoMassTapAdapter` | 2MASS PSC via IRSA | — | ✅ | `irsa.ipac.caltech.edu` |

Gaia DR3 and 2MASS do not have a human-readable name index.  `lookup_object()` automatically uses a **two-step strategy**: SIMBAD/NED resolve the name to a position, then Gaia DR3 and 2MASS cone-search around that position for multi-wavelength enrichment.

```bash
pip install -e .[live]
```

```python
import asyncio
from astrobridge.lookup import lookup_object

async def main():
    obj = await lookup_object("Proxima Centauri")
    if obj:
        print(obj.primary_name, obj.ra, obj.dec)
        print("catalogs:", list(obj.catalog_entries.keys()))
        print("photometry:", obj.photometry_summary)

asyncio.run(main())
```

Direct adapter usage:

```python
from astrobridge.connectors import SimbadTapAdapter, GaiaDR3TapAdapter
from astrobridge.models import Coordinate

async def main():
    # Name lookup — SIMBAD
    simbad = SimbadTapAdapter()
    hits = await simbad.query_object("M31")
    print("SIMBAD hits:", len(hits))

    # Positional enrichment — Gaia DR3
    gaia = GaiaDR3TapAdapter()
    coord = Coordinate(ra=10.685, dec=41.269)
    stars = await gaia.cone_search(coord, radius_arcsec=30)
    print("Gaia stars:", len(stars))

asyncio.run(main())
```

## Test Coverage For Adapter Steps

Every adapter development step should include tests under [tests/](tests/).
Current live-adapter unit coverage is in [tests/test_live_adapters.py](tests/test_live_adapters.py) using injected fake TAP services so tests stay deterministic and network-independent. This suite now includes retry, timeout, and malformed-row fallback scenarios for both TAP adapters.

## Project Layout

* [demo.py](demo.py) - runnable walkthrough of the system
* [astrobridge/models.py](astrobridge/models.py) - domain models
* [astrobridge/routing/](astrobridge/routing) - NLP routing and catalog ranking
* [astrobridge/matching/](astrobridge/matching) - Bayesian matching and calibration
* [astrobridge/api/](astrobridge/api) - orchestration and schemas

## Status

The repository currently passes its full test suite (261/261) in the default virtual environment when the dev dependencies are installed.

## Handoff Notes

Use [WORKLOG.md](WORKLOG.md) as the running implementation journal for future contributors.
Store run/test validation artifacts in [logs/](logs/) for reproducible handoff checkpoints.

The next major step is implementing real catalog connectors and unskipping integration tests that currently depend on live connector behavior.
Simbad and NED now include deterministic local implementations for `query_object` and `cone_search`, and integration matching tests run without skips.

The next major step is adding multi-attribute weighted matching controls (for example spatial + photometric weighting profiles) and exposing these controls through the API layer.