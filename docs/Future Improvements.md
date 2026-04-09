# AstroBridge: Future Improvements & Technical Recommendations

**Version**: v0.3.0 (April 9, 2026)  
**Scope**: Planned enhancements for v0.3.1 and beyond

---

## Priority 1: Critical Math & Physics Issues

### 1. Spherical Geometry (Not Flat-Sky Euclidean)

**Current Issue**:
- Catalog connectors and `BayesianMatcher` use flat-sky Euclidean distance
- Fine for tiny angular separations, but breaks at ≥1° scales
- Fails completely near RA boundaries (0/360°) and celestial poles

**Impact**:
- Distance calculations give wrong results for wide-field queries
- Matching probabilities diverge from reality for large separations
- Wide-area survey matching produces incorrect cross-matches

**Recommendation**:
```python
# Replace Euclidean distance with Haversine or use astropy
from astropy.coordinates import SkyCoord
import astropy.units as u

# Current (WRONG for large angles):
distance_deg = sqrt((ra1 - ra2)^2 + (dec1 - dec2)^2)

# Future (CORRECT spherical):
coord1 = SkyCoord(ra=ra1*u.deg, dec=dec1*u.deg)
coord2 = SkyCoord(ra=ra2*u.deg, dec=dec2*u.deg)
distance_deg = coord1.separation(coord2).deg
```

**Files to Update**:
- `astrobridge/matching/spatial.py` — Grid index distance calculations
- `astrobridge/matching/probabilistic.py` — Likelihood computation
- `astrobridge/geometry.py` — Core distance utilities

**Estimated Effort**: Medium (2-3 hours)

---

### 2. Fix Bayesian Math (Probability Normalization)

**Current Issue**:
The `BayesianMatcher` claims to do Bayesian cross-matching but makes **massive simplifying assumptions**:
- Assumes P(data) is constant across all candidates (it's not)
- Doesn't compute marginal likelihood ∫P(data|match)P(match)dθ
- Multiplies two independent Gaussians + prior, then clamps to 1.0
- **Result**: When two candidates have identical positions, both get high scores instead of sharing probability

**Mathematical Problem**:
```
Current (WRONG):
  P(match|data) ∝ P(data|match) × P(data|noMatch) × P(match)
                ∝ exp(-(Δpos²/σ²)) × exp(-(Δmag²/σ²)) × 0.7
  Clamped to [0, 1]: does NOT enforce ∑P(match|data) ≤ 1.0 across candidates

Correct (Bayesian):
  P(match|data) = P(data|match) × P(match) / P(data)
  where P(data) = ∑_i P(data|match_i) × P(match_i)
  
  Ensures: For a single reference source, ∑_j P(match_j|data) ≤ 1.0
```

**Impact**:
- Ambiguous matches (multiple good candidates) produce over-confident scores
- No proper probabilistic way to assign sources to candidates
- Marginal likelihood bias toward more data combinations

**Recommendation**:
- Implement proper Bayesian cross-matching: Compute P(data) from all candidate pairs
- Normalize posterior to enforce sum constraint
- Consider Hungarian algorithm or proper Bayesian network for 1-to-many assignment

**Files to Update**:
- `astrobridge/matching/probabilistic.py` — Core matcher logic
- `astrobridge/matching/base.py` — Abstract interface if needed

**Estimated Effort**: Medium-High (4-6 hours, requires mathematical review)

---

### 3. Proper-Motion Epoch Transformation (Rigorous)

**Current Status**: Already implemented with clamping, but verify:
- Test epoch transformations near Galactic plane (higher velocity stars)
- Validate against Gaia `pm_ra_cosdec` convention
- Add uncertainty propagation for PM errors

**Files**: `astrobridge/matching/probabilistic.py` — `_coordinate_at_epoch()`

---

## Priority 2: Concurrency & System Architecture

### 4. Async Library Integration (Replace Thread Blocking)

**Current Issue**:
- `SimbadTapAdapter` and `NedTapAdapter` use `asyncio.to_thread()` to wrap synchronous `pyvo` calls
- While preventing event loop freeze, it's a band-aid solution
- Under high load, thread pool exhausts (default 32 workers)
- Semaphore (max_concurrency=8) is the only thing preventing collapse

**Impact**:
- Fragile concurrency model
- No backpressure when thread pool saturates
- Harder to debug under production load

**Recommendation**:
- Migrate to async TAP client (if available in newer `pyvo`)
- Or: Implement proper thread pool management with backpressure
- Or: Queue-based architecture with worker pool size matching system capacity

**Files to Update**:
- `astrobridge/connectors.py` — `SimbadTapAdapter`, `NedTapAdapter`

**Estimated Effort**: High (6-8 hours, requires async library research)

---

### 5. OpenTelemetry Integration

**Current Status**:
- `AnalyticsStore` tracks events and timing
- No structured observability for async/concurrent operations

**Recommendation**:
```python
# Add OpenTelemetry tracing for Orchestrator
from opentelemetry import trace, metrics

@trace.get_tracer(__name__).start_as_current_span("execute_query")
async def execute_query(self, request: QueryRequest) -> QueryResponse:
    # Spans for each step: routing, querying, matching, scoring
    with trace.get_tracer(__name__).start_as_current_span("route_catalogs"):
        ...
    with trace.get_tracer(__name__).start_as_current_span("query_adapter"):
        ...
```

**Benefits**:
- Distributed tracing across async tasks
- Integration with Jaeger, DataDog, New Relic, etc.
- Production debugging visibility

**Files to Update**:
- `astrobridge/api/orchestrator.py` — Instrumentation points
- `astrobridge/connectors.py` — Adapter-level spans
- `astrobridge/matching/probabilistic.py` — Matching spans

**Estimated Effort**: Medium (3-4 hours)

---

## Priority 3: Router Intelligence & NLP

### 6. Replace Keyword Filter with Real NLP

**Current Issue**:
- `NLPQueryRouter` is **not NLP at all**, just hardcoded keyword lists:
  ```python
  if any(kw in query_lower for kw in self.STAR_KEYWORDS):
      return ObjectClass.STAR
  ```
- Fails on negations ("Not a star" → classified as STAR)
- No semantic understanding

**Recommendation**:
- Use lightweight embeddings model (sentence-transformers, MiniLM)
- Compare query against catalog descriptions
  ```python
  from sentence_transformers import SentenceTransformer
  
  model = SentenceTransformer("all-MiniLM-L6-v2")
  
  query_embedding = model.encode("Find red dwarf stars")
  catalog_embeddings = {
      "Gaia": model.encode("Gaia astrometry for stars"),
      "SIMBAD": model.encode("Comprehensive stellar catalog"),
      "NED": model.encode("Extragalactic galaxies and AGN"),
  }
  
  similarities = {
      name: cosine_similarity(query_embedding, embed)
      for name, embed in catalog_embeddings.items()
  }
  ```

**Benefits**:
- Handles negations, synonyms, semantic drift
- Scales to new object types without code changes
- Competitive with production NLP systems

**Tradeoff**:
- Model size ~26 MB (acceptable for optional `[nlp]` extra)
- Inference latency ~20-50ms (negligible in async context)

**Files to Update**:
- `astrobridge/routing/intelligent.py` — Replace STAR_KEYWORDS, etc.
- `pyproject.toml` — Add optional `[nlp]` extra

**Estimated Effort**: Medium (3-4 hours)

---

## Priority 4: Data Quality & Robustness

### 7. Fix Brittle Demo Data (SimbadConnector / NEDConnector)

**Current Issue**:
- `SimbadConnector` and `NEDConnector` return hardcoded local sources only for "Proxima Centauri"
- Any other query returns empty list with no warning
- Users don't realize they're not hitting live data

**Recommendation**:
- Either:
  1. **Option A**: Remove fake connectors entirely, document `[live]` as required for real usage
  2. **Option B**: Implement fallback behavior:
     ```python
     async def query_object(self, query: str) -> List[Source]:
         # Try live TAP if available
         if self._tap_service:
             try:
                 return await self._query_tap(query)
             except Exception as e:
                 logger.warning(f"TAP failed: {e}, returning empty")
         
         # Log warning if hardcoded fallback triggered
         if query.lower() == "proxima centauri":
             logger.warning("Using hardcoded data; install [live] for real queries")
             return self._hardcoded_sources
         
         return []
     ```

**Files to Update**:
- `astrobridge/connectors.py` — `SimbadConnector`, `NEDConnector`
- `README.md` — Clarify `[live]` requirement

**Estimated Effort**: Low (1-2 hours)

---

### 8. Add Haversine Distance Utility

**Current Status**: Flat-sky geometry referenced throughout  
**Action**: Create `astrobridge/geometry.py` with proper spherical functions:

```python
def haversine_distance(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """
    Haversine formula for angular distance on sphere (in degrees).
    Handles RA wrap-around and pole singularities correctly.
    """
    from math import radians, sin, cos, atan2, sqrt
    
    ra1, dec1, ra2, dec2 = map(radians, [ra1, dec1, ra2, dec2])
    
    delta_dec = dec2 - dec1
    delta_ra = ra2 - ra1
    
    # Handle RA wrap-around
    if delta_ra > pi:
        delta_ra = delta_ra - 2*pi
    elif delta_ra < -pi:
        delta_ra = delta_ra + 2*pi
    
    # Haversine
    a = sin(delta_dec/2)**2 + cos(dec1)*cos(dec2)*sin(delta_ra/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return degrees(c)
```

**Files to Update**:
- Create `astrobridge/geometry.py`
- Update imports in `spatial.py`, `probabilistic.py`

**Estimated Effort**: Low (1 hour)

---

## Priority 5: Testing & Validation

### 9. Add Regression Tests for Known Astronomical Cases

**Current**: Tests use synthetic data.  
**Recommendation**: Add integration tests with published astronomical benchmarks:

```python
# tests/integration/test_published_cases.py

def test_gaia_simbad_cross_match():
    """
    Test against published Gaia-SIMBAD cross-match sample.
    Validates matching at 0.1 arcsec precision.
    """
    ...

def test_ned_2mass_photometry():
    """
    Test photometric cross-match against published NED-2MASS pairs.
    """
    ...
```

**Estimated Effort**: Medium (4-5 hours, requires data curation)

---

### 10. Add Type Hints for All Remaining Modules

**Current**: Strict mypy on 3 core modules; relaxed elsewhere.  
**Recommendation**: Expand strict mode to all modules:

```bash
mypy --strict astrobridge/
```

**Estimated Effort**: Low-Medium (2-3 hours)

---

## Priority 6: Performance & Scalability

### 11. Index Optimization for Large Catalogs

**Current**: Spatial grid works for ~10K sources; may slow for 100K+.  
**Recommendation**: Benchmark and optimize:
- Consider KD-tree for large catalogs
- Adaptive grid based on source density
- Caching strategies for repeated queries

**Estimated Effort**: High (8+ hours)

---

## v0.3.1 Roadmap (Recommended)

**Must-Have**:
1. ✅ Spherical geometry (Haversine/astropy)
2. ✅ Fix Bayesian normalization
3. ✅ Replace keyword filter with embeddings-based NLP

**Should-Have**:
4. Real NLP router
5. OpenTelemetry tracing
6. Fix fake connector warnings

**Nice-to-Have**:
7. Async TAP library upgrade
8. Performance benchmarking
9. Type hints across all modules

**Estimated Timeline**: 2-3 weeks for priority 1-3, then incremental addition of 4-6.

---

## Notes for Reviewers

- **Math Review Needed**: Priority 2 (Bayesian) should be reviewed by domain expert before implementation
- **Backward Compatibility**: Breaking changes in Matcher interface acceptable for v0.4.0
- **Documentation**: Update Architecture Guide with corrected math once Priority 2 is resolved
- **Testing**: Expand test suite from 148 → 200+ once spherical geometry implemented

---

**Last Updated**: April 9, 2026  
**Next Review**: After v0.3.1 implementation
