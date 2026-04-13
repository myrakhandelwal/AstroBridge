# AstroBridge Test Suite Summary

**Version**: v0.3.0 (April 13, 2026)
**Total Tests**: 261 (all passing ✅)
**Execution Time**: ~1–2 seconds
**Coverage**: Core functionality, edge cases, error handling, concurrency, new catalogs

---

## Test Organization

### 1. Core Feature Tests

#### test_identify.py (7 tests)
- Object identification and classification
- Unknown object handling
- Hint-based detection for known designations

#### test_confidence_scoring.py (14 tests)
- Confidence score calculation
- Weighting profiles (balanced, position_first, photometry_first)
- Score explanation generation
- Edge cases (identical positions, far separations)

#### test_matcher.py (15 tests)
- Bayesian probabilistic matching
- Spatial indexing and nearest-neighbor queries
- Proper-motion-aware epoch transformations
- Cross-catalog matching scenarios
- Deterministic output validation

#### test_routing.py (36 tests)
- NLP query parsing and object classification
- Catalog ranking by object type across all 13 catalog types
- 8 object classes (STAR, GALAXY, QUASAR, NEBULA, etc.)
- Catalog strength scoring and property modifiers
- Natural language edge cases

#### test_edge_cases.py (21 tests)
- Boundary conditions (RA wrap-around, poles)
- Empty query results
- Malformed input handling
- Extreme coordinate values
- Missing optional fields

#### test_api.py (27 tests)
- Query request validation
- Response schema correctness
- Multi-catalog orchestration
- Error aggregation
- Matcher control propagation
- Schema backward compatibility

#### test_web.py (8 tests)
- FastAPI endpoint responses
- Request/response serialization
- Error handling and HTTP status codes
- HTML rendering
- Query persistence

#### test_persistence.py (2 tests)
- SQLite state store serialization
- Data survival across re-instantiation

#### test_live_adapters.py (8 tests)
- SIMBAD and NED TAP service integration
- Timeout and retry behavior
- Malformed row handling
- Bounded concurrency (Semaphore)

#### test_integration/ (1 test)
- Full pipeline: orchestration → matching → scoring

#### test_regression/ (1 test)
- Determinism validation

---

### 2. Interactive Demo Tests (34 tests)
**File**: `tests/test_interactive_demo.py`

#### TestInteractiveDemoSetup (2 tests)
- Orchestrator initialization with local connectors
- Orchestrator initialization with live TAP adapters

#### TestNameQuery (3 tests)
#### TestCoordinateQuery (3 tests)
#### TestNaturalLanguageQuery (3 tests)
#### TestObjectIdentification (4 tests)
#### TestMatcherControls (4 tests)
#### TestBenchmarking (3 tests)
#### TestErrorHandling (3 tests)
#### TestInputValidation (5 tests)
#### TestConcurrentQueries (2 tests)
#### TestOutputFormatting (2 tests)

---

### 3. Database Module Tests (16 tests)
**File**: `tests/test_database.py`

- Schema initialization and idempotency
- `upsert_object` / `get_object` round-trip
- Case-insensitive name lookup
- AI description persistence and preservation
- Catalog source insertion and retrieval
- Calibration frame registration, update, and lookup
- Invalid frame type validation
- Multi-frame listing

---

### 4. CCD Calibration Tests (8 tests)
**File**: `tests/test_ccd_calibration.py`

- `_has_astropy()` / `_has_ccdproc()` return bool
- `_resolve_frame_path` with env var, database, and missing-file cases
- `calibrate_ccd` raises `FileNotFoundError` for missing raw file
- No-frames path returns raw file unchanged
- `date_obs=None` uses today's date without error
- `output_dir` parameter forwarded correctly

---

### 5. AI Description Tests (21 tests)
**File**: `tests/test_ai_description.py`

- `_build_prompt` includes name, type, photometry, catalogs, alternate names
- `_call_stub` returns deterministic output with AI_PROVIDER hint
- `_cache_key` is stable and 16 chars
- `generate_description` with stub provider (with/without conn)
- Force-refresh skips cache
- Unknown provider falls back to stub
- `UnifiedObject.from_sources` round-trip (also covers models.py)

---

### 6. New Catalogs Tests (40 tests)
**File**: `tests/test_new_catalogs.py`

#### CatalogType enum (2 tests)
- All 5 new enum values present (TWOMASS, HIPPARCOS, ALLWISE, VIZIER, EXOPLANET_ARCHIVE)
- Total catalog count ≥ 13

#### CatalogRanker routing scores (6 tests)
- 2MASS and AllWISE present for all 8 object classes
- Gaia in top-3 for stars
- 2MASS boosted by `nir` property
- Exoplanet Archive boosted by `exoplanet` property
- ATLAS scores ≥ 0.75 for supernovae

#### NLP keyword extraction (2 tests)
- `nir` keyword triggers `nir` property
- `tess`/`exoplanet` triggers `exoplanet` property

#### GaiaDR3TapAdapter (8 tests)
- `query_object` returns empty list (no name index)
- Cone search returns Gaia DR3 source
- Proper motions (pmra, pmdec) propagated to `Coordinate`
- G, BP, RP photometry bands all present
- Zero-radius cone search returns empty
- TAP error silenced, returns empty
- RuntimeError raised when pyvo not installed

#### TwoMassTapAdapter (8 tests)
- `query_object` returns empty list (no name index)
- Cone search returns 2MASS source
- J, H, Ks photometry bands all present
- Zero-radius cone search returns empty
- TAP error silenced, returns empty
- RuntimeError raised when pyvo not installed

#### lookup.py integration (3 tests)
- `lookup_object` offline finds Proxima Centauri
- `lookup_object` returns None for nonexistent object
- `lookup_by_coordinates` offline returns list

---

## Test Coverage by Component

| Component | Tests | Status |
|-----------|-------|--------|
| Models (Coordinate, Source, UnifiedObject, etc.) | 10+ | ✅ |
| Routing (NLPQueryRouter, 13 catalogs) | 44 | ✅ |
| Matchers (BayesianMatcher, ConfidenceScorer) | 29 | ✅ |
| Connectors (Local + 4 Live TAP adapters) | 24 | ✅ |
| Lookup (live two-step fan-out) | 3 | ✅ |
| API (Orchestrator, QueryRequest/Response) | 27 | ✅ |
| Web (FastAPI endpoints) | 8 | ✅ |
| Persistence (SQLite — jobs, analytics, objects) | 18 | ✅ |
| CCD Calibration | 8 | ✅ |
| AI Description (stub + provider dispatch) | 21 | ✅ |
| Identification (Object classification) | 7 | ✅ |
| Benchmarking | 3 | ✅ |
| Interactive Demo | 34 | ✅ |
| Edge Cases & Error Handling | 24+ | ✅ |
| Concurrency & Stress | 10+ | ✅ |
| **Total** | **261** | **✅ All Passing** |

---

## Running Tests

```bash
pytest              # All tests
pytest -q           # Quiet summary
pytest -v           # Verbose (test names)
pytest -x           # Stop on first failure

# Specific files
pytest tests/test_new_catalogs.py -v
pytest tests/test_database.py -v
pytest tests/test_ai_description.py -v
pytest tests/test_matcher.py tests/test_routing.py -v

# Specific class
pytest tests/test_new_catalogs.py::GaiaDR3TapAdapter -v
```

---

## CI/CD Integration

All 261 tests run automatically in GitHub Actions on every PR/push:

```yaml
# .github/workflows/publish.yml
1. ruff check .          # Linting
2. mypy astrobridge/     # Type checking
3. pytest                # All 261 tests (< 2 seconds)
```

All gates must pass before merging to main.

---

**Last Updated**: April 13, 2026
**Total tests**: 261 (all passing)
