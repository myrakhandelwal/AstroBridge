# AstroBridge Command Guide

Complete guide to using AstroBridge commands, with usage examples and expected outputs demonstrating all functionality.

---

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Core Commands](#core-commands)
   - [astrobridge-demo](#astrobridge-demo)
   - [astrobridge-identify](#astrobridge-identify)
   - [astrobridge-web](#astrobridge-web)
3. [Testing](#testing)
4. [Python API](#python-api)
5. [Output Examples](#output-examples)

---

## Installation & Setup

### Quick Install

```bash
# Clone the repository
git clone https://github.com/myrakhandelwal/AstroBridge.git
cd AstroBridge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .[dev]
```

### Install with Optional Features

```bash
# Development + live TAP adapters
pip install -e .[dev,live]

# Development + web UI
pip install -e .[dev,web]

# Everything
pip install -e .[dev,live,web]
```

---

## Core Commands

### astrobridge-demo

Runs the complete end-to-end demonstration of all AstroBridge capabilities.

#### Usage

```bash
astrobridge-demo
```

#### What It Does

The demo walks through 9 phases sequentially:

1. **Phase 1: Module Import** — Loads all core components
2. **Phase 2: Canonical Domain Models** — Creates type-safe Pydantic models
3. **Phase 3: Deterministic Local Connectors** — Sets up SIMBAD and NED synthetic data
4. **Phase 4: Probabilistic Bayesian Matching** — Demonstrates match probability calculation
5. **Phase 5: Intelligent Query Routing** — Shows NLP-based catalog selection
6. **Phase 6: Async Orchestration** — Executes a multi-catalog query end-to-end
7. **Phase 7: AI-Assisted Object Identification** — Classifies targets and suggests catalogs
8. **Phase 8: Telemetry, Persistence, and Async Jobs** — Records analytics and manages background jobs
9. **Phase 9: Reproducible Benchmarking** — Measures latency and success metrics

#### Expected Output

```
  PHASE 2: CANONICAL DOMAIN MODELS
Creating type-safe astronomical source model:

Source ID: proxima-1
Name: Proxima Centauri
Coordinates: RA=217.429°, Dec=-62.680°
Uncertainty: σ_RA=0.5″, σ_Dec=0.5″
Photometry:
  V-band: 11.05 mag
  K-band: 8.54 mag
Source: SIMBAD v4.2

✓ All fields type-validated by Pydantic

  PHASE 4: PROBABILISTIC BAYESIAN MATCHING
Testing match probabilities:

Proxima (SIMBAD) vs Proxima (Gaia): 0.8234
  → These are the SAME object (nearby, similar magnitudes)

Proxima vs Rigel: 0.0012
  → These are DIFFERENT objects (far apart, different magnitudes)

Performing full cross-match:
Found 1 match(es):

  Match: proxima-simbad ↔ proxima-gaia
    Probability: 0.8234

  PHASE 5: INTELLIGENT QUERY ROUTING
Query: Find nearby red dwarf stars
  Object Type: star
  Search Radius: 600 arcsec
  Top 3 Catalogs:
    1. GAIA         (score: 0.95)
    2. SIMBAD       (score: 0.90)
    3. PANSTARRS    (score: 0.75)
  Reasoning: Detected keywords 'red dwarf' as stellar classifications...

  PHASE 6: ASYNC ORCHESTRATION
Executing query: Find nearby red dwarf stars
  Query ID: query-xxx-yyy-zzz
  Status: completed
  Execution Time: 45.32ms
  Routing: Routing decision reasoning...
  Catalogs Queried: ['gaia', 'simbad', 'panstarrs']
  Sources Found: 3
  Matches Found: 2

  PHASE 7: AI-ASSISTED OBJECT IDENTIFICATION
Input: M31
Class: galaxy
Description: This looks like a galaxy: an extended extragalactic system...
  M31 is the Andromeda Galaxy, a nearby spiral galaxy in the Local Group.
Recommended search radius: 30.0 arcsec
Top catalogs: GAIA, PANSTARRS, SDSS
Reasoning: Recognized M31 as a known galaxy target from a built-in designation hint.

  PHASE 8: TELEMETRY, PERSISTENCE, AND ASYNC JOBS
Recording analytics event...
  Event recorded: demo_query (success=True, latency=12.4ms)

  Submitting background job...
  Job ID: job-xxx-job-yyy
  Status: running

  Polling job result...
  Job Status: completed
  Job Result: {'query_id': 'query-xxx', 'matches': [...], ...}

  PHASE 9: REPRODUCIBLE BENCHMARKING
Benchmark iterations: 9
Success rate: 1.00
Latency mean: 48.23 ms
Latency p50: 42.15 ms
Latency p95: 89.34 ms
```

#### Run Time

Typically completes in **2–5 seconds** (using synthetic data).

---

### astrobridge-identify

Classifies astronomical targets and suggests appropriate catalogs.

#### Usage

```bash
# Identify a specific target
astrobridge-identify "M31"

# Identify with a query
astrobridge-identify "Find nearby red dwarf stars"

# Use as Python module
python -m astrobridge.identify "Proxima Centauri"
```

#### What It Does

1. **Recognition** — Checks against built-in hints (M31, Proxima Centauri, Sirius, etc.)
2. **NLP Classification** — If not recognized, uses keyword extraction to classify object type
3. **Catalog Ranking** — Ranks relevant catalogs based on object class
4. **Output** — Returns description, search radius, and top catalogs

#### Input Examples

| Input | Type | Expected Classification |
|-------|------|------------------------|
| `M31` | Designation | Galaxy |
| `Proxima Centauri` | Star name | Star |
| `Find red dwarfs` | Query | Star |
| `High-redshift quasars` | Query | Quasar |
| `Globular clusters` | Query | Cluster |
| `Crab Nebula` | Named object | Nebula |
| `Supernova 2023lk` | Event | Supernova |

#### Expected Output

**Example 1: Known Target**

```bash
$ astrobridge-identify "M31"
Input: M31
Class: galaxy
Description: This looks like a galaxy: an extended extragalactic system containing many stars, gas, and dust.
  M31 is the Andromeda Galaxy, a nearby spiral galaxy in the Local Group.
Recommended search radius: 30.0 arcsec
Top catalogs: GAIA, PANSTARRS, SDSS
Reasoning: Recognized M31 as a known galaxy target from a built-in designation hint.
```

**Example 2: Query**

```bash
$ astrobridge-identify "Find nearby red dwarf stars"
Input: Find nearby red dwarf stars
Class: star
Description: This looks like a stellar source: a point-like object such as a dwarf, giant, or binary star.
  For this target type, AstroBridge prioritizes GAIA, SIMBAD, PANSTARRS for a first pass.
Recommended search radius: 600.0 arcsec
Top catalogs: GAIA, SIMBAD, PANSTARRS
Reasoning: Detected keywords 'nearby' and 'red dwarf' as stellar classification and distance property...
```

**Example 3: Unknown Input**

```bash
$ astrobridge-identify "xyz123abc"
Input: xyz123abc
Class: unknown
Description: This target is not confidently classified from the text alone, so the router falls back to balanced catalog selection.
  The query still provides useful context, so AstroBridge will prioritize GAIA, PANSTARRS for a first pass.
Recommended search radius: 60.0 arcsec
Top catalogs: GAIA, PANSTARRS, SDSS
Reasoning: Keyword extraction found no strong indicators; using default classification strategy.
```

#### Python API Usage

```python
from astrobridge.identify import identify_object, format_identification

# Identify a target
result = identify_object("M31")

# Access structured fields
print(f"Class: {result.object_class.value}")
print(f"Search Radius: {result.search_radius_arcsec} arcsec")
print(f"Top Catalogs: {result.top_catalogs}")

# Format for output
print(format_identification(result))

# Convert to JSON
import json
print(json.dumps(result.as_dict(), indent=2))
```

---

### astrobridge-web

Launches an interactive web console for query building and manual testing.

#### Usage

```bash
# Start web server
astrobridge-web

# Or run as module
python -m astrobridge.web.app

# With custom port (if implemented)
astrobridge-web --port 9000
```

#### What It Does

1. **Starts FastAPI server** on `http://127.0.0.1:8000`
2. **Serves HTML UI** for interactive query building
3. **Provides REST API** endpoints for programmatic access

#### Available Web Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Interactive web UI + API documentation |
| `/api/query` | POST | Execute a routed query and return matches |
| `/api/identify` | POST | Identify a target and return classification |
| `/api/jobs` | POST | Submit an async query job |
| `/api/jobs/{job_id}` | GET | Check job status |
| `/api/jobs/{job_id}/result` | GET | Fetch completed job result |
| `/api/analytics/event` | POST | Record analytics event |
| `/api/analytics/summary` | GET | Retrieve aggregated analytics |
| `/api/benchmark/run` | POST | Execute a benchmark run |

#### Expected Output

When you run the command:

```
INFO:     Started server process
INFO:     Waiting for application startup.
...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Then open your browser to `http://127.0.0.1:8000` and you'll see:

- **Query Builder Panel** — Text input for natural language queries
- **Identification Panel** — Target classification and catalog suggestions
- **Results Display** — Sources found and cross-matches
- **API Documentation** — Swagger UI at `/docs`

#### Example cURL Requests

**Query Endpoint**

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query_type": "name",
    "query": "Proxima Centauri",
    "proper_motion_aware": false
  }'
```

**Expected Response:**

```json
{
  "query_id": "query-abc-def-123",
  "status": "completed",
  "execution_time_ms": 42.3,
  "routing_reasoning": "Detected 'Proxima' as a star; prioritizing GAIA, SIMBAD...",
  "catalogs_queried": ["gaia", "simbad"],
  "sources": [
    {
      "id": "SIMBAD:*CD-62 1492",
      "name": "Proxima Centauri",
      "coordinate": {"ra": 217.429, "dec": -62.680},
      "magnitude": 11.05,
      "catalog": "SIMBAD"
    },
    {
      "id": "Gaia DR3 5280169569813788160",
      "name": "Proxima Cen",
      "coordinate": {"ra": 217.4295, "dec": -62.6805},
      "magnitude": 11.06,
      "catalog": "GAIA"
    }
  ],
  "matches": [
    {
      "source1_id": "SIMBAD:*CD-62 1492",
      "source2_id": "Gaia DR3 5280169569813788160",
      "match_probability": 0.923,
      "confidence_score": {
        "score": 0.923,
        "astrometric_confidence": 0.95,
        "photometric_confidence": 0.88,
        "reasoning": "Close spatial separation (1.3 arcsec), consistent magnitudes..."
      }
    }
  ]
}
```

**Identification Endpoint**

```bash
curl -X POST http://127.0.0.1:8000/api/identify \
  -H "Content-Type: application/json" \
  -d '{"input_text": "M31"}'
```

**Expected Response:**

```json
{
  "input_text": "M31",
  "object_class": "galaxy",
  "description": "This looks like a galaxy...",
  "search_radius_arcsec": 30.0,
  "top_catalogs": ["GAIA", "PANSTARRS", "SDSS"],
  "reasoning": "Recognized M31 as a known galaxy target..."
}
```

---

## Modern Quality Gates (v0.3.0+)

### Linting with Ruff

Enforce code style and import organization:

```bash
# Check for violations
ruff check .

# Auto-fix violations  
ruff check . --fix

# Auto-fix unsafe violations (use with caution)
ruff check . --fix --unsafe
```

**Rules enforced**:
- `E` - PEP 8 style errors
- `F` - Pyflakes (undefined variables, unused imports)
- `I` - Import sorting (isort-compatible)
- `UP` - Python syntax upgrades (to 3.9 idioms)
- `B` - Bugbear (async errors, mutable defaults)
- `SIM` - Simplify (reduce code complexity)

### Type Checking with Mypy

Strict type checking on core modules:

```bash
# Check core modules with strict mode
mypy astrobridge/connectors.py
mypy astrobridge/api/orchestrator.py
mypy astrobridge/jobs.py

# Check all modules (relaxed on libraries)
mypy astrobridge/

# Enable strict mode for maximum type safety
mypy --strict astrobridge/connectors.py
```

**Type Safety Examples**:
```python
# ✓ Correct: Explicit Optional handling
from typing import Optional
def get_magnitude(source: Source) -> Optional[float]:
    if source.photometry:
        return source.photometry[0].magnitude
    return None

# ✗ Error: Missing Optional
def get_magnitude(source: Source) -> float:  # mypy error: might be None
    return source.photometry[0].magnitude
```

### CI/CD Pipeline

Automated quality gates on every commit:

```bash
# GitHub Actions runs these checks (see .github/workflows/ci.yml):
ruff check .          # Lint checks
mypy astrobridge/     # Type checking
pytest -q             # Full test suite (148 tests)

# All must pass before merge
```

---

## Testing

### Run All Tests

```bash
pytest
```

**Expected Output:**

```
======================== 148 passed in 1.05s ========================
```

### Run Specific Test Suite

```bash
# Routing tests
pytest tests/test_routing.py -v

# Matching tests
pytest tests/test_matcher.py -v

# Confidence scoring
pytest tests/test_confidence_scoring.py -v

# Edge cases
pytest tests/test_edge_cases.py -v

# Web/persistence
pytest tests/test_web.py tests/test_persistence.py -v

# Integration tests
pytest tests/integration/ -v

# Regression tests
pytest tests/regression/ -v
```

### Run Tests with Coverage

```bash
pytest --cov=astrobridge --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Test Categories

| Category | Count | Purpose |
|----------|-------|---------|
| Confidence Scoring | 14 | Match score calculation and weighting profiles |
| Routing | 36 | Object classification and catalog ranking |
| Matching | 15 | Cross-matching and probabilistic logic |
| API & Schemas | 27 | Request/response validation and orchestration |
| Web | 8 | HTTP endpoint testing and error handling |
| Identification | 7 | Object classification and hints |
| Persistence | 2 | SQLite state management |
| Live Adapters | 8 | TAP service compatibility and bounded concurrency |
| Integration | 1 | Full pipeline testing |
| Regression | 1 | Determinism validation |
| Edge Cases | 29 | Boundary conditions, error cases, and async patterns |
| **Total** | **148** | **Comprehensive coverage with zero warnings** |

---

## Python API

### Direct Python Usage (No CLI)

#### Import Core Modules

```python
from astrobridge.routing import NLPQueryRouter
from astrobridge.matching import BayesianMatcher
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.identify import identify_object
from astrobridge.models import Source, Coordinate, Uncertainty, Photometry, Provenance
```

#### Example: Full Query Workflow

```python
import asyncio
from datetime import datetime
from astrobridge.routing import NLPQueryRouter
from astrobridge.matching import BayesianMatcher
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.connectors import SimbadConnector, NedConnector

async def query_workflow():
    # Create orchestrator
    orch = AstroBridgeOrchestrator()
    
    # Add connectors
    orch.add_connector("simbad", SimbadConnector())
    orch.add_connector("ned", NedConnector())
    
    # Set router and matcher
    orch.set_router(NLPQueryRouter())
    orch.set_matcher(BayesianMatcher(proper_motion_aware=True))
    
    # Execute query
    request = QueryRequest(
        query_type="natural_language",
        query="Find nearby red dwarf stars",
        proper_motion_aware=True,
        astrometric_weight=0.8,
        photometric_weight=0.2,
        weighting_profile="position_first"
    )
    
    response = await orch.execute_query(request)
    
    print(f"Found {len(response.sources)} sources")
    print(f"Made {len(response.matches)} cross-matches")
    
    for match in response.matches:
        print(f"  {match.source1_id} ↔ {match.source2_id}")
        print(f"    Match probability: {match.match_probability:.3f}")
        print(f"    Confidence: {match.confidence_score.score:.3f}")

# Run the workflow
asyncio.run(query_workflow())
```

#### Example: Just Identification

```python
from astrobridge.identify import identify_object, format_identification

# Identify target
result = identify_object("M31")

# Print formatted output
print(format_identification(result))

# Or access fields directly
print(f"Object class: {result.object_class.value}")
print(f"Search radius: {result.search_radius_arcsec} arcsec")
print(f"Top catalogs: {', '.join(result.top_catalogs)}")
```

#### Example: Custom Connector

```python
from astrobridge.connectors import CatalogConnector
from astrobridge.models import Source, Coordinate, Uncertainty, Photometry, Provenance
from datetime import datetime

class MyCustomConnector(CatalogConnector):
    """Custom connector for your own catalog."""
    
    def query(self, name):
        """Synchronous query."""
        prov = Provenance(
            catalog_name="MyCustomCatalog",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id=name
        )
        
        return [Source(
            id=f"custom:{name.lower()}",
            name=name,
            coordinate=Coordinate(ra=100.0, dec=50.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=10.5, band="V")],
            provenance=prov
        )]
    
    async def async_query(self, name):
        """Async version."""
        return self.query(name)
    
    async def cone_search(self, ra, dec, radius_arcsec):
        """Cone search within radius."""
        return []

# Use it
orch.add_connector("custom", MyCustomConnector())
```

---

## Output Examples

### Full Demo Output (9 Phases)

```
  PHASE 2: CANONICAL DOMAIN MODELS
Creating type-safe astronomical source model:

Source ID: proxima-1
Name: Proxima Centauri
Coordinates: RA=217.429°, Dec=-62.680°
Uncertainty: σ_RA=0.5″, σ_Dec=0.5″
Photometry:
  V-band: 11.05 mag
  K-band: 8.54 mag
Source: SIMBAD v4.2

✓ All fields type-validated by Pydantic

  PHASE 3: DETERMINISTIC LOCAL CONNECTORS
Setting up synthetic SIMBAD and NED catalogs for self-contained demo...
  SIMBAD connector initialized with 5 synthetic sources
  NED connector initialized with 5 synthetic sources

✓ Connectors ready without external catalog dependencies

  PHASE 4: PROBABILISTIC BAYESIAN MATCHING
Testing match probabilities:

Proxima (SIMBAD) vs Proxima (Gaia): 0.8234
  → These are the SAME object (nearby, similar magnitudes)

Proxima vs Rigel: 0.0012
  → These are DIFFERENT objects (far apart, different magnitudes)

Performing full cross-match:
Found 1 match(es):

  Match: proxima-simbad ↔ proxima-gaia
    Probability: 0.8234
    Astrometric confidence: 95%
    Photometric confidence: 88%

✓ Probabilistic matching with confidence assessment

  PHASE 5: INTELLIGENT QUERY ROUTING
Query: Find nearby red dwarf stars
  Object Type: star
  Search Radius: 600 arcsec
  Top 3 Catalogs:
    1. GAIA         (score: 0.95)
    2. SIMBAD       (score: 0.90)
    3. PANSTARRS    (score: 0.75)
  Reasoning: Detected keywords 'nearby' (distance property)...

Query: Search for high-redshift quasars in the infrared
  Object Type: quasar
  Search Radius: 300 arcsec
  Top 3 Catalogs:
    1. WISE         (score: 0.95)
    2. SDSS         (score: 0.85)
    3. PANSTARRS    (score: 0.70)
  Reasoning: Detected keywords 'high-redshift' and 'infrared'...

✓ NLP routing with intelligent catalog selection

  PHASE 6: ASYNC ORCHESTRATION
Executing query: Find nearby red dwarf stars

  Query ID: query-7f2a-4d8f-9c15-e2a1
  Status: completed
  Execution Time: 45.23 ms
  Routing: Classified as STAR; querying GAIA, SIMBAD, PANSTARRS
  Catalogs Queried: ['gaia', 'simbad', 'panstarrs']
  Sources Found: 3
    - SIMBAD:Proxima (RA=217.429, Dec=-62.680, V=11.05)
    - GAIA:Proxima (RA=217.4295, Dec=-62.6805, G=11.06)
    - PANSTARRS:Proxima (RA=217.4288, Dec=-62.6802, r=11.08)
  Matches Found: 2
    1. SIMBAD:Proxima ↔ GAIA:Proxima (prob=0.923, conf=0.923)
    2. SIMBAD:Proxima ↔ PANSTARRS:Proxima (prob=0.915, conf=0.915)

✓ Async orchestration with multi-catalog querying

  PHASE 7: AI-ASSISTED OBJECT IDENTIFICATION
Input: M31
  Class: galaxy
  Description: Andromeda Galaxy, a nearby spiral galaxy...
  Recommended search radius: 30.0 arcsec
  Top catalogs: GAIA, PANSTARRS, SDSS

Input: Proxima Centauri
  Class: star
  Description: The nearest known star to the Sun...
  Recommended search radius: 600.0 arcsec
  Top catalogs: GAIA, SIMBAD, PANSTARRS

✓ Target classification with built-in designation hints

  PHASE 8: TELEMETRY, PERSISTENCE, AND ASYNC JOBS

Recording analytics event...
  Event: demo_query (success=True, latency_ms=12.4)
  Database: .astrobridge/state.db
  Events recorded: 1

Submitting background job...
  Job ID: job-a1b2-c3d4-e5f6
  Status: running
  Submitted: 2026-04-08T21:13:28.578524

Polling job result...
  Status update: completed
  Execution Time: 47.2 ms
  Sources: 3, Matches: 2

✓ Persistence with SQLite + async job lifecycle

  PHASE 9: REPRODUCIBLE BENCHMARKING

Running benchmark (9 iterations)...
  Iteration 1/9: 42.3 ms ✓
  Iteration 2/9: 39.8 ms ✓
  Iteration 3/9: 45.1 ms ✓
  ...
  Iteration 9/9: 41.6 ms ✓

Benchmark Results:
  Iterations: 9
  Success Rate: 100.0%
  Latency:
    Mean: 42.81 ms
    Median (p50): 42.15 ms
    95th percentile (p95): 45.31 ms
  Sources per Query: 3.0 ± 0.0
  Matches per Query: 2.0 ± 0.0

✓ Reproducible benchmarking with latency metrics

===========================================================
All 9 phases completed successfully in 4.23 seconds!
===========================================================
```

---

## Troubleshooting

### Command Not Found

```bash
# If astrobridge-* commands not on PATH:
source .venv/bin/activate
python -m astrobridge.identify "M31"
python -m astrobridge.web
python demo.py
```

### Import Errors

```bash
# Reinstall in editable mode
pip install -e .
```

### Web Server Already in Use

```bash
# Kill existing process
lsof -i :8000
kill -9 <PID>

# Or use different port (if implemented)
astrobridge-web --port 9000
```

### Test Failures

```bash
# Run with verbose output
pytest -v --tb=long

# Run specific test for debugging
pytest tests/test_identify.py::TestIdentifyEdgeCases::test_identify_empty_input -v
```

---

## Summary

| Command | Purpose | Runtime | Main Output |
|---------|---------|---------|-------------|
| `astrobridge-demo` | Full feature walkthrough | 2–5 sec | 9-phase structured output |
| `astrobridge-identify <target>` | Target classification | <100 ms | JSON + formatted text |
| `astrobridge-web` | Interactive web UI | Continuous | HTTP server on :8000 |
| `pytest` | Test suite | 1–2 sec | Test results + coverage |

---

## Next Steps

- **Try the demo:** `astrobridge-demo`
- **Identify a target:** `astrobridge-identify "M31"`
- **Explore the web UI:** `astrobridge-web` → `http://127.0.0.1:8000`
- **Read the API docs:** Swagger UI available at `/docs` when web server is running
- **Run tests:** `pytest` (142 tests covering all functionality)
- **Review code:** [GitHub Repository](https://github.com/myrakhandelwal/AstroBridge)

