# AstroBridge Test Suite Summary

**Version**: v0.3.0 (April 9, 2026)  
**Total Tests**: 182 (all passing ✅)  
**Execution Time**: ~1-2 seconds  
**Coverage**: Core functionality, edge cases, error handling, concurrency

---

## Test Organization

### 1. Core Feature Tests (Original Suite: 148 tests)

#### test_identify.py (7 tests)
- Object identification and classification
- Unknown object handling
- Hint-based detection

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
- Catalog ranking by object type
- 8 object classes (STAR, GALAXY, QUASAR, NEBULA, etc.)
- Catalog strength scoring
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
- TAP service integration
- Timeout and retry behavior
- Malformed row handling
- Request/response parsing
- Bounded concurrency (Semaphore)

#### test_integration/ (1 test)
- Full pipeline: orchestration → matching → scoring

#### test_regression/ (1 test)
- Determinism validation

---

### 2. Interactive Demo Tests (New: 34 tests)
**File**: `tests/test_interactive_demo.py`

Comprehensive testing of interactive demo functionality covering all menu options.

#### TestInteractiveDemoSetup (2 tests)
- Orchestrator initialization with local connectors
- Orchestrator initialization with live TAP adapters

#### TestNameQuery (3 tests)
- Query "Proxima Centauri" (well-known object)
- Query "M31" (galaxy)
- Query unknown object (graceful handling)

#### TestCoordinateQuery (3 tests)
- Cone search around Proxima Centauri
- Large radius search (600″)
- Small radius search (10″)

#### TestNaturalLanguageQuery (3 tests)
- Query for stars: "Find nearby red dwarf stars"
- Query for galaxies: "Find faint galaxies"
- Negation edge case: "Not a star"

#### TestObjectIdentification (4 tests)
- Identify "Proxima Centauri" (star)
- Identify "M31" (galaxy)
- Identify unknown input ("xyz123unknown")
- Format identification results

#### TestMatcherControls (4 tests)
- Balanced weighting profile
- Position-first weighting
- Photometry-first weighting
- Proper-motion-aware matching

#### TestBenchmarking (3 tests)
- Benchmark configuration validation
- Benchmark runner execution (2 iterations)
- Statistics collection and ordering

#### TestErrorHandling (3 tests)
- Query with empty results
- Multiple catalog partial failure
- Coordinate boundary validation

#### TestInputValidation (5 tests)
- Object name handling (arbitrary strings)
- RA bounds validation (0-360°)
- Dec bounds validation (-90 to +90°)
- Radius validation (positive numbers)
- Query type validation (name, coordinates, natural_language)

#### TestConcurrentQueries (2 tests)
- 3 concurrent name queries
- 2 concurrent coordinate queries

#### TestOutputFormatting (2 tests)
- Source object display formatting
- MatchResult object display formatting

---

## Test Coverage by Component

| Component | Tests | Status |
|-----------|-------|--------|
| Models (Coordinate, Source, Photometry, etc.) | 10+ | ✅ |
| Routers (NLPQueryRouter) | 36 | ✅ |
| Matchers (BayesianMatcher, ConfidenceScorer) | 29 | ✅ |
| Connectors (Local + Live TAP) | 8+ | ✅ |
| API (Orchestrator, QueryRequest/Response) | 27 | ✅ |
| Web (FastAPI endpoints) | 8 | ✅ |
| Persistence (SQLite) | 2 | ✅ |
| Identification (Object classification) | 7 | ✅ |
| Benchmarking | 3 | ✅ |
| Interactive Demo (Menu options) | 34 | ✅ |
| Edge Cases & Error Handling | 24+ | ✅ |
| Concurrency & Stress | 10+ | ✅ |
| **Total** | **182** | **✅ All Passing** |

---

## Running Tests

### All Tests
```bash
pytest              # Run all tests
pytest -v           # Verbose output (test names)
pytest -q           # Quiet (summary only)
pytest -x           # Stop on first failure
```

### Specific Test Files
```bash
pytest tests/test_interactive_demo.py -v
pytest tests/test_matcher.py -v
pytest tests/test_routing.py -v
pytest tests/test_api.py -v
pytest tests/test_confidence_scoring.py -v
```

### Specific Test Class
```bash
pytest tests/test_interactive_demo.py::TestNameQuery -v
pytest tests/test_interactive_demo.py::TestMatcherControls -v
```

### With Coverage Report
```bash
pytest --cov=astrobridge --cov-report=html
open htmlcov/index.html  # View HTML report
```

### Async Tests Only
```bash
pytest -k "asyncio" -v
```

### Run Tests in Parallel (faster)
```bash
pip install pytest-xdist
pytest -n auto  # Use all CPU cores
```

---

## Test Categories & Their Purpose

### Unit Tests
- Validate individual components in isolation
- Test math correctness (matching, scoring)
- Verify data model constraints

### Integration Tests
- Test multi-component workflows
- Verify API contract between layers
- Validate end-to-end query pipelines

### Regression Tests
- Ensure deterministic output
- Prevent performance degradation
- Catch breaking changes

### Edge Case Tests
- Boundary conditions (RA wrap, poles)
- Empty/None inputs
- Extreme values
- Malformed data

### Stress Tests
- Concurrent queries
- Large result sets
- Multiple iterations

### Interactive Demo Tests
- Validate all menu options work correctly
- Test user input handling
- Verify output formatting
- Catch runtime errors early

---

## Key Test Scenarios

### 1. Name Query Flow
```
User input: "Proxima Centauri"
  ↓
Orchestrator routes to SIMBAD, NED
  ↓
Both catalogs query successfully
  ↓
Sources parsed into unified format
  ↓
Cross-matching applied
  ↓
Confidence scores calculated
  ↓
Results returned to user
```
**Tests**: test_interactive_demo.py::TestNameQuery

### 2. Cone Search Flow
```
User input: RA=217.429, Dec=-62.680, Radius=60″
  ↓
Orchestrator initiates coordinate query
  ↓
Catalogs perform cone search
  ↓
Results filtered by radius
  ↓
Sources returned sorted by separation
```
**Tests**: test_interactive_demo.py::TestCoordinateQuery

### 3. Natural Language Flow
```
User input: "Find nearby red dwarf stars"
  ↓
Router parses text → STAR + stellar keywords
  ↓
Router ranks catalogs → [SIMBAD, GAIA, PANSTARRS]
  ↓
Queried catalogs in order
  ↓
Cross-match results
```
**Tests**: test_interactive_demo.py::TestNaturalLanguageQuery

### 4. Matcher Controls Flow
```
User input: Same object, different weighting profiles
  ↓
Profile 1: Balanced (0.5 astrometric, 0.5 photometric)
  ↓
Profile 2: Position-first (0.8 astrometric, 0.2 photometric)
  ↓
Profile 3: Photometry-first (0.2 astrometric, 0.8 photometric)
  ↓
Confidence scores differ per profile
```
**Tests**: test_interactive_demo.py::TestMatcherControls

### 5. Benchmarking Flow
```
User input: iterations=3
  ↓
Runner executes 3 queries
  ↓
Latencies recorded: [140ms, 135ms, 145ms]
  ↓
Statistics calculated:
    Mean: 140ms
    P50: 140ms
    P95: 145ms
    Max: 145ms
```
**Tests**: test_interactive_demo.py::TestBenchmarking

---

## CI/CD Integration

All 182 tests run automatically in GitHub Actions on every PR/push:

```yaml
# .github/workflows/ci.yml
1. ruff check .          # Linting
2. mypy astrobridge/     # Type checking
3. pytest                # All 182 tests (< 2 seconds)
```

**All gates must pass** before merging to main.

---

## Test Maintenance

### Adding New Tests

1. **Identify what to test**: Feature, edge case, integration
2. **Create test function**: 
   ```python
   @pytest.mark.asyncio
   async def test_new_feature() -> None:
       """Test description."""
       # Arrange
       orchestrator = setup_orchestrator()
       
       # Act
       response = await orchestrator.execute_query(request)
       
       # Assert
       assert response.status == "success"
   ```
3. **Run test locally**: `pytest tests/test_file.py::test_new_feature -v`
4. **Commit with test**: Git includes test change in commit

### Fixing Failing Tests

1. **Understand failure**: Read error message
2. **Check recent changes**: What code changed?
3. **Fix code or test**:
   - If code has bug → fix code
   - If test has wrong expectation → fix test
4. **Re-run locally**: `pytest -x` (stop on first failure)
5. **Verify all pass**: `pytest`

### Performance Testing

```bash
# Run tests with timing
pytest tests/ --durations=10

# Identify slow tests and optimize
```

---

## Known Limitations & Skips

### Skipped Tests
- Live TAP adapter tests skip if `[live]` extra not installed
- Performance tests skip if system under heavy load

### Expected Failures
None currently (all tests pass).

---

## Test Statistics

- **Framework**: pytest + pytest-asyncio
- **Async Tests**: ~80 (async/await patterns)
- **Mock Tests**: ~10 (mocking external services)
- **Parametrized Tests**: ~15 (multiple scenarios per test)
- **Fixtures**: ~20 (shared test setup)

---

**Last Updated**: April 9, 2026  
**Next Review**: After implementing v0.3.1 improvements  
**Maintainers**: AstroBridge Development Team
