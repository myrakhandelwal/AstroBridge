# AstroBridge Example Usage

This guide shows practical end-to-end usage patterns for AstroBridge.

## 1. Install and run tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
```

## 2. Run the full demo pipeline

```bash
source .venv/bin/activate
python demo.py
```

The demo walks through:
- domain models
- intelligent routing
- probabilistic matching
- API orchestration
- object identification
- telemetry and background jobs
- benchmarking

## 3. Python API usage

### Name-based query

```python
import asyncio
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.connectors import SimbadConnector, NEDConnector
from astrobridge.routing import NLPQueryRouter

async def run_name_query() -> None:
    orchestrator = AstroBridgeOrchestrator()
    orchestrator.set_router(NLPQueryRouter())
    orchestrator.add_connector("simbad", SimbadConnector())
    orchestrator.add_connector("ned", NEDConnector())

    request = QueryRequest(
        query_type="name",
        name="Proxima Centauri",
        auto_route=True,
    )

    response = await orchestrator.execute_query(request)
    print(response.status)
    print("catalogs:", response.catalogs_queried)
    print("sources:", len(response.sources))
    print("matches:", len(response.matches))

asyncio.run(run_name_query())
```

### Natural-language query

```python
import asyncio
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.connectors import SimbadConnector, NEDConnector
from astrobridge.routing import NLPQueryRouter

async def run_nl_query() -> None:
    orchestrator = AstroBridgeOrchestrator()
    orchestrator.set_router(NLPQueryRouter())
    orchestrator.add_connector("simbad", SimbadConnector())
    orchestrator.add_connector("ned", NEDConnector())

    request = QueryRequest(
        query_type="natural_language",
        description="Find nearby red dwarf stars in infrared catalogs",
        auto_route=True,
    )

    response = await orchestrator.execute_query(request)
    print(response.routing_reasoning)
    for source in response.sources:
        print(source.name, source.provenance.catalog_name)

asyncio.run(run_nl_query())
```

### Coordinate cone-search query

```python
import asyncio
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.api.schemas import CoordinateRequest
from astrobridge.connectors import SimbadConnector, NEDConnector

async def run_coordinate_query() -> None:
    orchestrator = AstroBridgeOrchestrator()
    orchestrator.add_connector("simbad", SimbadConnector())
    orchestrator.add_connector("ned", NEDConnector())

    request = QueryRequest(
        query_type="coordinates",
        coordinates=CoordinateRequest(ra=217.429, dec=-62.680, radius_arcsec=30.0),
        auto_route=False,
        catalogs=["simbad", "ned"],
    )

    response = await orchestrator.execute_query(request)
    print(response.status)
    print("sources:", len(response.sources))

asyncio.run(run_coordinate_query())
```

## 4. Object identification helper

```python
from astrobridge.identify import identify_object, format_identification

result = identify_object("M31")
print(format_identification(result))
```

## 5. Telemetry and jobs

```python
from astrobridge.analytics import AnalyticsEvent, AnalyticsStore

store = AnalyticsStore(db_path="astrobridge_state.db", persist=True)
store.record(
    AnalyticsEvent(
        event_type="query",
        query_type="natural_language",
        user_level="advanced",
        success=True,
        latency_ms=12.3,
        catalog_count=3,
        metadata={"example": True},
    )
)
print(store.summary())
```

## 6. Benchmarking

```python
import asyncio
from astrobridge.benchmarking import BenchmarkConfig, BenchmarkRunner
from astrobridge.api import AstroBridgeOrchestrator

async def run_benchmark() -> None:
    orchestrator = AstroBridgeOrchestrator()
    runner = BenchmarkRunner(orchestrator)
    result = await runner.run(BenchmarkConfig(iterations=30))
    print(result)

asyncio.run(run_benchmark())
```

## 7. CLI quick start

If installed with entry points from setup:

```bash
astrobridge-demo
astrobridge-identify "M31"
astrobridge-web
```
