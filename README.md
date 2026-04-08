# AstroBridge

AstroBridge is a compact astronomical source matching pipeline that combines three pieces:

* type-safe source models for catalogs and coordinates
* intelligent query routing for catalog selection
* Bayesian cross-matching for candidate association

The repository also includes an async orchestration layer and a runnable demo so new users can see the full flow quickly.

## Quick Start

Create a virtual environment, install the package, then run the demo or tests.

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

## What You Get

* [astrobridge.models](astrobridge/models.py) for `Source`, `Coordinate`, `Uncertainty`, `Photometry`, and `Provenance`
* [astrobridge.routing](astrobridge/routing) for natural-language query routing
* [astrobridge.matching](astrobridge/matching) for probabilistic source matching
* [astrobridge.api](astrobridge/api) for request and response schemas plus orchestration

## Demo Flow

The demo script walks through the core phases in order:

1. canonical models
2. intelligent routing
3. Bayesian matching
4. async orchestration

It uses synthetic data so it can run without external catalog access.

## Development Notes

The test suite uses `pytest-asyncio`, which is included in the `dev` extra.

Live catalog connectors are scaffolded for extension. The current connector classes are intentionally lightweight placeholders, so production deployment should replace them with real catalog-backed implementations, rate limiting, and error handling appropriate to the target service.

## Project Layout

* [demo.py](demo.py) - runnable walkthrough of the system
* [astrobridge/models.py](astrobridge/models.py) - domain models
* [astrobridge/routing/](astrobridge/routing) - NLP routing and catalog ranking
* [astrobridge/matching/](astrobridge/matching) - Bayesian matching and calibration
* [astrobridge/api/](astrobridge/api) - orchestration and schemas

## Status

The repository currently passes its test suite in the default virtual environment when the dev dependencies are installed.

## Handoff Notes

Use [WORKLOG.md](WORKLOG.md) as the running implementation journal for future contributors.
Store run/test validation artifacts in [logs/](logs/) for reproducible handoff checkpoints.

The next major step is implementing real catalog connectors and unskipping integration tests that currently depend on live connector behavior.
The async connector surface (`query_object`, `cone_search`) is now scaffolded to support that implementation.