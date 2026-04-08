# AstroBridge

AstroBridge is a compact astronomical source matching pipeline that combines three pieces:

* type-safe source models for catalogs and coordinates
* intelligent query routing for catalog selection
* Bayesian cross-matching for candidate association

The repository also includes an async orchestration layer and a runnable demo so new users can see the full flow quickly.

Recent additions include confidence scoring for every match and optional proper-motion-aware epoch matching.

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

## Manuscript Draft

LaTeX manuscript draft for the AI/astronomy paper is available at [docs/astrobridge_ai_astronomy_paper.tex](docs/astrobridge_ai_astronomy_paper.tex).

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

## What You Get

* [astrobridge.models](astrobridge/models.py) for `Source`, `Coordinate`, `Uncertainty`, `Photometry`, and `Provenance`
* [astrobridge.routing](astrobridge/routing) for natural-language query routing
* [astrobridge.matching](astrobridge/matching) for probabilistic source matching
* [astrobridge.api](astrobridge/api) for request and response schemas plus orchestration

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

The demo script walks through the core phases in order:

1. canonical models
2. intelligent routing
3. Bayesian matching
4. async orchestration

It uses synthetic data so it can run without external catalog access.

## Development Notes

The test suite uses `pytest-asyncio`, which is included in the `dev` extra.

Simbad and NED currently use deterministic local datasets for fast, reliable development and CI validation.

## Live SIMBAD TAP Adapter

SIMBAD exposes a TAP service, and AstroBridge includes a live adapter for it: `SimbadTapAdapter` in [astrobridge/connectors.py](astrobridge/connectors.py).
AstroBridge also includes `NedTapAdapter` for NED TAP-style access in the same module.

Install live adapter dependency:

```bash
pip install -e .[live]
```

Example usage:

```python
import asyncio
from astrobridge.connectors import SimbadTapAdapter
from astrobridge.models import Coordinate

async def main():
	adapter = SimbadTapAdapter()

	by_name = await adapter.query_object("Prox Cen")
	print("name hits:", len(by_name))

	around = await adapter.cone_search(
		Coordinate(ra=217.429, dec=-62.680),
		radius_arcsec=60,
	)
	print("cone hits:", len(around))

asyncio.run(main())
```

NED adapter usage follows the same shape:

```python
from astrobridge.connectors import NedTapAdapter

adapter = NedTapAdapter()
```

Default TAP endpoint used:
- `https://simbad.cds.unistra.fr/simbad/sim-tap`
- `https://ned.ipac.caltech.edu/tap`

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

The repository currently passes its full test suite (98/98) in the default virtual environment when the dev dependencies are installed.

## Handoff Notes

Use [WORKLOG.md](WORKLOG.md) as the running implementation journal for future contributors.
Store run/test validation artifacts in [logs/](logs/) for reproducible handoff checkpoints.

The next major step is implementing real catalog connectors and unskipping integration tests that currently depend on live connector behavior.
Simbad and NED now include deterministic local implementations for `query_object` and `cone_search`, and integration matching tests run without skips.

The next major step is adding multi-attribute weighted matching controls (for example spatial + photometric weighting profiles) and exposing these controls through the API layer.