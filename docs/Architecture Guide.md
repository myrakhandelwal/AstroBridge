# AstroBridge: Architecture Guide for Research & Teaching

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Core Components](#core-components)
3. [Data Models & Type Safety](#data-models--type-safety)
4. [Orchestration Pipeline](#orchestration-pipeline)
5. [Design Patterns](#design-patterns)
6. [Advanced Usage Scenarios](#advanced-usage-scenarios)
7. [Building Custom Catalog Adapters](#building-custom-catalog-adapters)
8. [Integration Patterns](#integration-patterns)
9. [Reproducible Science Workflows](#reproducible-science-workflows)
10. [Visualization & Analysis](#visualization--analysis)
11. [Teaching with AstroBridge](#teaching-with-astrobridge)

---

## System Architecture Overview

AstroBridge is designed with **layered, composable architecture** suitable for both educational exploration and production research workflows.

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Interface Layer                         │
│  ┌─────────────────┬──────────────────┬────────────────┐       │
│  │  CLI Commands   │   FastAPI Web    │  Python API    │       │
│  │  (demo, id)     │   (REST + UI)    │  (import libs) │       │
│  └─────────────────┴──────────────────┴────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              Orchestration & Control Layer                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │   AstroBridgeOrchestrator                               │  │
│  │   - Query execution & lifecycle                         │  │
│  │   - Error handling & recovery                           │  │
│  │   - Job management (async/background)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        ↓                       ↓                      ↓
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   Router     │    │    Matcher       │    │ Connectors   │
│              │    │                  │    │              │
│ - NLP query  │    │ - Bayesian       │    │ - Gaia       │
│   parsing    │    │   matching       │    │ - 2MASS      │
│ - Catalog    │    │ - Confidence     │    │ - SIMBAD     │
│   selection  │    │   scoring        │    │ - NED        │
│              │    │ - Ambiguity      │    │ - Custom     │
│              │    │   resolution     │    │              │
└──────────────┘    └──────────────────┘    └──────────────┘
        ↓                       ↓                      ↓
┌─────────────────────────────────────────────────────────────────┐
│              Data Models (Pydantic v2)                           │
│  Source | Coordinate | Photometry | Uncertainty | Provenance   │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────────┐
│                 Persistence Layer (SQLite)                       │
│  Jobs | Analytics | Benchmarking Results | State Management    │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Composability**: Each component (router, matcher, connectors) is independent and swappable
2. **Type Safety**: Pydantic v2 models enforce structure at every boundary
3. **Async-First**: Concurrent catalog queries via asyncio
4. **Transparency**: Every decision (routing, matching, scoring) is logged and explainable
5. **Extensibility**: Custom adapters, weights, and algorithms can be plugged in
6. **Persistence**: State is tracked in SQLite for reproducibility and auditing

---

## Core Components

### 1. Orchestrator (`AstroBridgeOrchestrator`)

**Purpose**: Coordinates the entire query pipeline.

**Responsibilities**:
- Parse incoming requests
- Apply user-specified matcher controls
- Route to appropriate catalogs (automatic or explicit)
- Execute concurrent catalog queries
- Cross-match results
- Aggregate errors and successes
- Return structured responses

**Key Methods**:
```python
async execute_query(request: QueryRequest) -> QueryResponse
    # Main entry point for any astronomical query
    
async _query_catalog(query_id, catalog, request) -> List[Source]
    # Query a single catalog; handles auth, timeouts, error recovery
    
_cross_match_sources(all_sources: List[Source]) -> List[MatchResult]
    # Run Bayesian matching across all sources from all catalogs
    
_apply_matcher_controls(request: QueryRequest)
    # Set matcher thresholds based on user request
```

**Example Usage**:
```python
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.routing import IntelligentRouter
from astrobridge.matching import BayesianMatcher
from astrobridge.connectors import GaiaAdapter, SimBadAdapter

# Setup
router = IntelligentRouter()
matcher = BayesianMatcher(proper_motion_aware=True)
connectors = {
    "gaia": GaiaAdapter(),
    "simbad": SimBadAdapter(),
}

orchestrator = AstroBridgeOrchestrator(
    router=router,
    matcher=matcher,
    connectors=connectors
)

# Query
request = QueryRequest(
    query_type="name",
    name="Proxima Centauri",
    auto_route=True,
    confidence_threshold=0.5,
    astrometric_weight=0.8,
)

response = await orchestrator.execute_query(request)
print(f"Found {len(response.sources)} sources, {len(response.matches)} matches")
```

### 2. Router (`IntelligentRouter`)

**Purpose**: Classify astronomical targets and recommend catalogs.

**Algorithm**:
1. Parse query text via NLP (object name detection, type hints)
2. Classify object type (star, galaxy, quasar, nebula, cluster, AGN, SNE)
3. Rank catalogs by object type (see `CATALOG_STRENGTHS` matrix)
4. Return ranked list with reasoning

**Object Classes**:
- `STAR`: Individual stars, dwarf stars, binary components
- `GALAXY`: Spiral, elliptical, irregular galaxies
- `QUASAR`: QSO/AGN at high redshift
- `NEBULA`: Emission nebulae, HII regions, planetary nebulae
- `CLUSTER`: Globular clusters, open clusters, stellar associations
- `AGN`: Active galactic nuclei (lower redshift than quasars)
- `SNE`: Supernovae and transients

**Catalog Strengths Matrix**:
```python
CATALOG_STRENGTHS = {
    ObjectClass.STAR: {
        CatalogType.GAIA: 0.95,      # Best astrometry
        CatalogType.SIMBAD: 0.90,    # Comprehensive
        CatalogType.SDSS: 0.75,      # Photometry
        ...
    },
    ObjectClass.GALAXY: {
        CatalogType.NED: 0.95,       # Galaxy specialist
        CatalogType.SDSS: 0.85,      # Large survey
        ...
    },
    # ... more object types
}
```

**Teaching Application**: Use this to explain why different catalogs are optimal for different science goals.

### 3. Matcher (`BayesianMatcher`)

**Purpose**: Determine if sources from different catalogs are the same object.

**Core Algorithm**:
1. Build spatial index of candidates (unless proper-motion-aware)
2. For each reference source, find nearby candidates
3. Compute positional likelihood (Gaussian astrometry)
4. Compute photometric likelihood (magnitude matching)
5. Compute posterior probability via Bayes' theorem
6. Integrate confidence scorer for ambiguity handling
7. Return ranked matches

**Key Parameters**:
- `positional_sigma_threshold`: Max deviation (default 3.0σ)
- `confidence_threshold`: Min posterior probability (default 0.05)
- `prior_match_prob`: Prior that two sources match (default 0.7)
- `proper_motion_aware`: Account for stellar kinematics
- `match_epoch`: Common epoch for coordinate comparison

**Confidence Scorer** (`ConfidenceScorer`):
- Weights astrometric and photometric evidence
- Applies distance-ratio bonus for ambiguity
- Returns human-readable explanation

### 4. Connectors (Catalog Adapters)

**Purpose**: Query external astronomical databases and parse results into standardized `Source` objects.

**Interface** (`CatalogConnector`):
```python
class CatalogConnector(ABC):
    @abstractmethod
    async query_object(
        query: str,
        cone_search: Optional[ConeSearch] = None
    ) -> List[Source]:
        """Query by name or position."""
        
    @abstractmethod
    def parse_source(self, raw_record: Dict) -> Source:
        """Convert catalog record to Source model."""
```

**Included Adapters**:
- **GaiaAdapter**: Gaia mission astrometry (high precision)
- **SimBadAdapter**: SIMBAD (comprehensive, lower precision)
- **NedAdapter**: NASA Extragalactic Database (galaxies, AGN)
- **TwoMassAdapter**: 2MASS infrared photometry
- **WiseAdapter**: WISE infrared all-sky survey
- **SimbadTapAdapter**: Live TAP connection to SIMBAD (requires `[live]` extra)
- **NedTapAdapter**: Live TAP connection to NED (requires `[live]` extra)

**Uncertainty Handling**: 
Each adapter maps catalog-specific error columns to standardized `Uncertainty` model:
```python
# SIMBAD example
uncertainty = Uncertainty(
    ra_error=raw_record.get("RA_error", 0.1),        # Default 0.1 arcsec
    dec_error=raw_record.get("DEC_error", 0.1),
)
```

**Teaching Application**: Build adapters for student-collected data or specialized surveys.

---

## Data Models & Type Safety

All data flows through **Pydantic v2** models, which provide:
- Type validation at every boundary
- Automatic serialization (JSON/dict)
- IDE autocompletion and type checking
- Clear documentation via `Field` descriptions

### Core Models

#### `Coordinate`
```python
class Coordinate(BaseModel):
    ra: float                                 # Right ascension (degrees)
    dec: float                                # Declination (degrees)
    pm_ra_mas_per_year: Optional[float]      # Proper motion RA (mas/yr)
    pm_dec_mas_per_year: Optional[float]     # Proper motion Dec (mas/yr)
```

#### `Uncertainty`
```python
class Uncertainty(BaseModel):
    ra_error: float                # RA uncertainty (arcsec)
    dec_error: float               # Dec uncertainty (arcsec)
```

#### `Photometry`
```python
class Photometry(BaseModel):
    magnitude: float               # Magnitude value
    band: str                      # Filter band (V, J, K, etc.)
    magnitude_error: Optional[float]
```

#### `Provenance`
```python
class Provenance(BaseModel):
    catalog_name: str              # "Gaia", "SIMBAD", etc.
    catalog_version: str           # "DR3", "2023-11", etc.
    query_timestamp: datetime      # When source was retrieved
    source_id: str                 # Catalog's internal ID
```

#### `Source`
```python
class Source(BaseModel):
    id: str                        # Unique ID (catalog-specific)
    name: str                      # Source name
    coordinate: Coordinate         # Position + proper motion
    uncertainty: Uncertainty       # Astrometric errors
    photometry: List[Photometry]   # Multi-band measurements
    provenance: Provenance         # Metadata
```

#### `MatchResult`
```python
class MatchResult(BaseModel):
    source1_id: str               # First source
    source2_id: str               # Second source
    match_probability: float      # Posterior P(match|data)
    separation_arcsec: float      # Angular separation
    confidence: float             # Aggregated confidence score
```

### Type-Driven Benefits

**Example: Type-safe proper-motion correction**

```python
# Without type safety: string parsers, try/except everywhere
catalog_pm_ra = catalog_record.get("pm_ra")  # Could be None, str, or float
if catalog_pm_ra and isinstance(catalog_pm_ra, str):
    try:
        pm_ra = float(catalog_pm_ra.split()[0])
    except:
        pm_ra = None
# ... error-prone

# With Pydantic:
coord = Coordinate(
    ra=123.456,
    dec=-45.678,
    pm_ra_mas_per_year=10.5,    # Type-checked immediately
)
```

---

## Orchestration Pipeline

### Query Execution Flow

```
User Request (QueryRequest)
         ↓
[1] Parse & Validate
    - Schema validation (Pydantic)
    - Apply defaults
    - Check constraint compatibility
         ↓
[2] Route (if auto_route=True)
    - Parse query text
    - Classify object type
    - Rank catalogs
    - Select top N (default: 3)
         ↓
[3] Query Catalogs (AsyncIO)
    - Launch concurrent tasks
    - For each catalog:
      * Apply catalog-specific filters
      * Stringify query for remote API
      * Parse remote response
      * Convert to Source models
    - Gather results (all succeed/fail independently)
         ↓
[4] Cross-Match (if 2+ catalogs)
    - Flatten all sources into single list
    - Apply matcher controls (thresholds, weights)
    - For each reference source:
      * Build spatial index of candidates
      * Compute likelihoods (position, photometry)
      * Return top match (if posterior > threshold)
         ↓
[5] Score & Rank
    - Compute confidence for each match
    - Build explanation string
    - Sort by confidence
         ↓
[6] Aggregate Response
    - Deduplicate sources (same object from multiple catalogs)
    - Aggregate photometry
    - Return QueryResponse with:
      * sources (deduplicated list)
      * matches (cross-matched pairs)
      * errors (per-catalog failures)
      * timing (query duration)
         ↓
QueryResponse to User
```

### Error Handling Strategy

**Resilience**: AstroBridge uses **graceful degradation**:

1. **Per-catalog failures**: One catalog timing out doesn't fail the entire query
2. **Partial matching**: If 2 of 3 catalogs succeed, return matches from the 2
3. **Explicit error reporting**: All errors accumulated in `response.errors` field

**Example**:
```python
response = await orchestrator.execute_query(request)

# Gaia succeeded, SIMBAD timed out, NED had parse error
print(f"Sources: {len(response.sources)}")  # Gaia + NED results
print(f"Matches: {len(response.matches)}")  # Cross-match of Gaia ↔ NED
print(f"Errors: {response.errors}")         # ["simbad: timeout", "ned: parse error"]
```

---

## Design Patterns

### 1. Adapter Pattern (Catalog Connectors)

Each catalog has a different API format. AstroBridge uses **adapters** to normalize them:

```python
# All adapters implement this interface
class CatalogConnector(ABC):
    async query_object(query: str, cone_search: Optional[ConeSearch] = None) -> List[Source]:
        pass
```

**Example: Custom ESO Archive Adapter**
```python
from astrobridge.connectors import CatalogConnector
from astrobridge.models import Source, Coordinate, Uncertainty

class ESOArchiveAdapter(CatalogConnector):
    """Query ESO Archive for observational data."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://archive.eso.org/eso/eso_archive_adp.html"
    
    async def query_object(self, query: str, cone_search=None) -> List[Source]:
        # ESO-specific query logic
        # Parse ESO response format
        # Convert to Source objects
        return [Source(...), Source(...)]
    
    def parse_source(self, raw_record: Dict) -> Source:
        return Source(
            id=raw_record["eso_ref"],
            name=raw_record["target"],
            coordinate=Coordinate(
                ra=float(raw_record["ra"]),
                dec=float(raw_record["dec"]),
            ),
            # ... more fields
        )
```

### 2. Strategy Pattern (Matching Algorithms)

Users can swap matching algorithms without changing orchestration code:

```python
# Default: Bayesian matching
matcher = BayesianMatcher(positional_sigma_threshold=3.0)

# Alternative: Positional-only (fast, less accurate)
matcher = BayesianMatcher(photometric_weight=0.0)

# Alternative: Probability-conservative
matcher = BayesianMatcher(prior_match_prob=0.3)

orchestrator = AstroBridgeOrchestrator(
    router=router,
    matcher=matcher,  # Swappable strategy
    connectors=connectors,
)
```

### 3. Factory Pattern (Confidence Scorers)

Pre-configured scoring strategies for different use cases:

```python
# Balanced for general stellar surveys
scorer = ConfidenceScorer.from_profile("balanced")

# Position-heavy for astrometry
scorer = ConfidenceScorer.from_profile("position_first")

# Photometry-heavy for variability studies
scorer = ConfidenceScorer.from_profile("photometry_first")

# Custom weights
scorer = ConfidenceScorer(
    astrometric_weight=0.6,
    photometric_weight=0.4,
)
```

### 4. Observer Pattern (Analytics)

Events are tracked without coupling to business logic:

```python
from astrobridge.analytics import AnalyticsStore

analytics = AnalyticsStore()

# Log events automatically
analytics.record_event({
    "event_type": "query_executed",
    "query_type": "name",
    "num_sources": 150,
    "num_matches": 42,
    "duration_ms": 523,
})

# Query later for telemetry
summary = analytics.get_summary()
print(f"Total queries: {summary['total_queries']}")
print(f"Avg sources per query: {summary['avg_sources']}")
```

---

## Advanced Usage Scenarios

### Scenario 1: Proper-Motion-Aware Matching Across Epochs

**Problem**: Cross-matching a catalog from 2015 with modern Gaia DR3 (2021). Stellar proper motions can shift positions by several arcseconds.

**Solution**:

```python
from datetime import datetime
from astrobridge.matching import BayesianMatcher

# Proper-motion-aware matching
matcher = BayesianMatcher(
    proper_motion_aware=True,
    match_epoch=datetime(2018, 1, 1),  # Match at this common epoch
)

# Sources with proper motions from each catalog
old_sources = [Source(..., coordinate=Coordinate(ra=..., pm_ra_mas_per_year=5.0)), ...]
gaia_sources = [Source(...), ...]

# Matcher internally transforms coordinates to 2018-01-01
matches = matcher.match(old_sources, gaia_sources)

for match in matches:
    print(f"{match.source1_id} → {match.source2_id}: "
          f"confidence={match.confidence:.2f}, "
          f"separation={match.separation_arcsec:.2f} arcsec")
```

**What Happens Under the Hood**:
1. For each old source, compute position at 2018-01-01 using stored proper motion
2. For each Gaia source, compute position at 2018-01-01 (may use catalog proper motion)
3. Compare positions at common epoch
4. Resolve matches probabilistically

### Scenario 2: Multi-Wavelength Photometric SED Matching

**Problem**: Match sources across Gaia (optical), 2MASS (infrared), and WISE (mid-IR) using color information.

**Solution**:

```python
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest

orchestrator = AstroBridgeOrchestrator(
    router=router,
    matcher=BayesianMatcher(
        astrometric_weight=0.6,  # Less weight on position
        photometric_weight=0.4,  # More weight on colors
        confidence_threshold=0.3, # Be permissive (few matches across surveys)
    ),
    connectors={
        "gaia": GaiaAdapter(),
        "2mass": TwoMassAdapter(),
        "wise": WiseAdapter(),
    }
)

# Request forces all three catalogs
request = QueryRequest(
    query_type="coordinates",
    ra=123.456,
    dec=-45.678,
    search_radius_arcsec=30,
    catalogs=["gaia", "2mass", "wise"],
    auto_route=False,  # Use all three
)

response = await orchestrator.execute_query(request)

# Now you have multi-wavelength SEDs
for match in response.matches:
    source1 = next(s for s in response.sources if s.id == match.source1_id)
    source2 = next(s for s in response.sources if s.id == match.source2_id)
    
    # Merge photometry
    all_mags = source1.photometry + source2.photometry
    print(f"Multi-band SED for {source1.name}:")
    for phot in all_mags:
        print(f"  {phot.band}: {phot.magnitude:.2f} ± {phot.magnitude_error:.2f}")
```

### Scenario 3: Crowded Field Disambiguation

**Problem**: In a globular cluster, many stars cluster within the search radius. Distinguish true matches from coincidental projections.

**Solution**:

```python
# Tighter sigma threshold + lower prior
matcher = BayesianMatcher(
    positional_sigma_threshold=2.0,  # Stricter positional requirement
    prior_match_prob=0.3,            # Fewer false positives in dense regions
    confidence_scorer=ConfidenceScorer.from_profile("position_first"),
)

matches = matcher.match(hst_sources, ground_based_sources)

# Inspect runner-up separations to understand ambiguity
for match in matches:
    if match.confidence < 0.7:
        print(f"⚠ Ambiguous match: {match.source1_id} → {match.source2_id}")
        print(f"  Confidence: {match.confidence:.2f}")
        print(f"  Separation: {match.separation_arcsec:.3f} arcsec")
        print(f"  Recommend visual inspection")
```

### Scenario 4: Variability Detection

**Problem**: Find stars that have changed significantly in magnitude between epochs.

**Solution**:

```python
from astrobridge.models import Source

# Query two epochs separately
request_2020 = QueryRequest(
    query_type="cone_search",
    ra=123.456, dec=-45.678,
    search_radius_arcsec=60,
    catalogs=["panstarrs"],
)

request_2024 = QueryRequest(
    query_type="cone_search",
    ra=123.456, dec=-45.678,
    search_radius_arcsec=60,
    catalogs=["ztf"],  # ZTF is current
)

sources_2020 = (await orchestrator.execute_query(request_2020)).sources
sources_2024 = (await orchestrator.execute_query(request_2024)).sources

# Cross-match
matches = matcher.match(sources_2020, sources_2024)

# Find variables
for match in matches:
    s1 = next(s for s in sources_2020 if s.id == match.source1_id)
    s2 = next(s for s in sources_2024 if s.id == match.source2_id)
    
    # Get same-band magnitude if available
    mag_2020 = next((p.magnitude for p in s1.photometry if p.band == "r"), None)
    mag_2024 = next((p.magnitude for p in s2.photometry if p.band == "r"), None)
    
    if mag_2020 and mag_2024:
        delta_mag = abs(mag_2024 - mag_2020)
        if delta_mag > 0.5:  # > 0.5 mag change
            print(f"Variable: {s1.name}")
            print(f"  2020: {mag_2020:.2f} mag (r-band)")
            print(f"  2024: {mag_2024:.2f} mag (r-band)")
            print(f"  Δmag: {delta_mag:.2f} mag")
```

---

## Building Custom Catalog Adapters

### Step 1: Understand the Interface

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from astrobridge.models import Source
from astrobridge.matching.base import ConeSearch

class CatalogConnector(ABC):
    """Base class for catalog adapters."""
    
    @abstractmethod
    async def query_object(
        self,
        query: str,
        cone_search: Optional[ConeSearch] = None,
    ) -> List[Source]:
        """Query catalog by name or region."""
        pass
```

### Step 2: Example - Local CSV Catalog

```python
import asyncio
import pandas as pd
from datetime import datetime
from astrobridge.models import Source, Coordinate, Uncertainty, Photometry, Provenance
from astrobridge.connectors import CatalogConnector

class LocalCSVAdapter(CatalogConnector):
    """Query a local CSV file as a catalog."""
    
    def __init__(self, csv_path: str, catalog_name: str = "LocalCSV"):
        self.df = pd.read_csv(csv_path)
        self.catalog_name = catalog_name
        self.catalog_version = "1.0"
    
    async def query_object(
        self,
        query: str,
        cone_search=None,
    ) -> List[Source]:
        """
        Query by object name or cone search.
        
        Args:
            query: Object name or "CONE(RA, DEC, RADIUS)"
            cone_search: ConeSearch object with RA, Dec, radius
            
        Returns:
            List of Source objects
        """
        results = []
        
        if cone_search:
            # Cone search mode
            ra, dec = cone_search.ra, cone_search.dec
            radius = cone_search.radius_arcsec / 3600.0  # Convert to degrees
            
            # Filter by distance
            mask = (
                ((self.df["ra"] - ra) ** 2 +
                 (self.df["dec"] - dec) ** 2) ** 0.5
            ) < radius
            
            matches = self.df[mask]
        else:
            # Name search – fuzzy matching
            matches = self.df[
                self.df["name"].str.contains(query, case=False, regex=False)
            ]
        
        # Convert rows to Source objects
        for _, row in matches.iterrows():
            source = self.parse_source(row.to_dict())
            results.append(source)
        
        return results
    
    def parse_source(self, raw_record: Dict) -> Source:
        """Convert CSV row to Source."""
        
        # Extract coordinates and uncertainties
        coord = Coordinate(
            ra=float(raw_record["ra"]),
            dec=float(raw_record["dec"]),
            pm_ra_mas_per_year=float(raw_record.get("pm_ra", None)),
            pm_dec_mas_per_year=float(raw_record.get("pm_dec", None)),
        )
        
        uncertainty = Uncertainty(
            ra_error=float(raw_record.get("ra_err", 0.1)),
            dec_error=float(raw_record.get("dec_err", 0.1)),
        )
        
        # Extract photometry (assume CSV has columns like "mag_u", "mag_g", etc.)
        photometry = []
        for band in ["u", "g", "r", "i", "z"]:
            mag_col = f"mag_{band}"
            err_col = f"mag_{band}_err"
            if mag_col in raw_record:
                photometry.append(Photometry(
                    magnitude=float(raw_record[mag_col]),
                    band=band,
                    magnitude_error=float(raw_record.get(err_col, None)),
                ))
        
        provenance = Provenance(
            catalog_name=self.catalog_name,
            catalog_version=self.catalog_version,
            query_timestamp=datetime.now(),
            source_id=str(raw_record.get("id", raw_record["name"])),
        )
        
        return Source(
            id=str(raw_record.get("id", raw_record["name"])),
            name=str(raw_record["name"]),
            coordinate=coord,
            uncertainty=uncertainty,
            photometry=photometry,
            provenance=provenance,
        )

# Usage
adapter = LocalCSVAdapter("my_star_catalog.csv", catalog_name="MyLocalSurvey")
sources = await adapter.query_object("Prox Cen")
```

### Step 3: Example - REST API Adapter

```python
import aiohttp
import logging
from typing import List, Optional, Dict, Any
from astrobridge.connectors import CatalogConnector
from astrobridge.models import Source

logger = logging.getLogger(__name__)

class CustomRESTAdapter(CatalogConnector):
    """Query a custom REST API catalog."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.catalog_name = "CustomREST"
    
    async def query_object(
        self,
        query: str,
        cone_search=None,
    ) -> List[Source]:
        """Query custom REST API."""
        
        async with aiohttp.ClientSession() as session:
            if cone_search:
                # Cone search endpoint
                url = f"{self.base_url}/cone"
                params = {
                    "ra": cone_search.ra,
                    "dec": cone_search.dec,
                    "radius": cone_search.radius_arcsec / 3600.0,
                }
            else:
                # Name search endpoint
                url = f"{self.base_url}/search"
                params = {"query": query}
            
            # Add auth if needed
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            try:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"API returned {resp.status}")
                        return []
                    
                    data = await resp.json()
                    
                    # Parse response (assumes data["sources"] is list of records)
                    return [
                        self.parse_source(record)
                        for record in data.get("sources", [])
                    ]
            
            except aiohttp.ClientError as e:
                logger.error(f"API request failed: {e}")
                return []
    
    def parse_source(self, raw_record: Dict) -> Source:
        # Custom parsing logic for your API's JSON format
        return Source(...)
```

---

## Integration Patterns

### Pattern 1: Data Pipeline Integration

Embed AstroBridge in a larger data processing pipeline:

```python
import asyncio
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
import pandas as pd

async def enrich_catalog(csv_file: str, orchestrator: AstroBridgeOrchestrator) -> pd.DataFrame:
    """Enrich a local catalog with Gaia data."""
    
    df = pd.read_csv(csv_file)
    enriched_rows = []
    
    for idx, row in df.iterrows():
        request = QueryRequest(
            query_type="coordinates",
            ra=row["ra"],
            dec=row["dec"],
            search_radius_arcsec=10,
            catalogs=["gaia"],
        )
        
        response = await orchestrator.execute_query(request)
        
        # Add Gaia data to row
        if response.sources:
            gaia_source = response.sources[0]  # Closest match
            row["gaia_parallax"] = gaia_source.coordinate.parallax
            row["gaia_magnitude"] = gaia_source.photometry[0].magnitude
            row["match_confidence"] = response.matches[0].confidence if response.matches else 0.0
        
        enriched_rows.append(row)
        
        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1}/{len(df)} objects")
    
    return pd.DataFrame(enriched_rows)

# Use it:
enriched = await enrich_catalog("my_catalog.csv", orchestrator)
enriched.to_csv("my_catalog_enriched.csv", index=False)
```

### Pattern 2: Batch Processing with Results Caching

Avoid re-querying the same region:

```python
import hashlib
import json
from typing import Dict, List

class CachedOrchestrator:
    """Orchestrator with local query caching."""
    
    def __init__(self, orchestrator: AstroBridgeOrchestrator, cache_dir: str = ".cache"):
        self.orchestrator = orchestrator
        self.cache_dir = cache_dir
        self.cache = {}
    
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """Execute query, checking cache first."""
        
        # Create cache key from request
        key_str = json.dumps(request.model_dump(), sort_keys=True, default=str)
        cache_key = hashlib.md5(key_str.encode()).hexdigest()
        
        # Check memory cache
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Execute query
        response = await self.orchestrator.execute_query(request)
        
        # Cache result
        self.cache[cache_key] = response
        
        return response

# Use it:
cached_orch = CachedOrchestrator(orchestrator)

# First call: executes query
resp1 = await cached_orch.execute_query(request)

# Second call: returns cached result
resp2 = await cached_orch.execute_query(request)  # Fast!
```

### Pattern 3: Async/Await for Production Workflows

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def process_survey_async(
    orchestrator: AstroBridgeOrchestrator,
    coordinates: List[Tuple[float, float]],
    batch_size: int = 50,
) -> List[QueryResponse]:
    """Process many coordinates concurrently."""
    
    tasks = []
    for ra, dec in coordinates:
        request = QueryRequest(
            query_type="coordinates",
            ra=ra,
            dec=dec,
            search_radius_arcsec=30,
        )
        tasks.append(orchestrator.execute_query(request))
    
    # Process in batches to avoid overwhelming the system
    responses = []
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        batch_results = await asyncio.gather(*batch)
        responses.extend(batch_results)
        
        # Progress reporting
        print(f"Processed {len(responses)}/{len(tasks)} objects")
    
    return responses

# Usage
coords = [(ra, dec) for ra, dec in ...]  # Your coordinates
responses = await process_survey_async(orchestrator, coords, batch_size=50)
```

---

## Reproducible Science Workflows

### Workflow 1: Published Matching Study

Goal: Match a historical catalog to modern surveys, publish results with full reproducibility.

```python
"""
Cross-match historical catalog (1995 epoch) with Gaia DR3.
Publication: "Smith et al. (2026): Modern Astrometry of Historical Objects"
"""

import asyncio
import logging
from datetime import datetime
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.matching import BayesianMatcher
from astrobridge.benchmarking import BenchmarkRunner

# Configure logging for audit trail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cross_match_study.log"),
        logging.StreamHandler(),
    ]
)

async def main():
    # Reproducibility: versions and config
    print("=" * 70)
    print("CROSS-MATCH STUDY: Historical Catalog → Gaia DR3")
    print("=" * 70)
    print(f"Execution date: {datetime.now()}")
    print(f"AstroBridge version: 0.1.1")
    print(f"Gaia version: DR3")
    print("=" * 70)
    
    # Setup with explicit parameters
    matcher = BayesianMatcher(
        positional_sigma_threshold=3.0,
        confidence_threshold=0.05,
        prior_match_prob=0.7,
        proper_motion_aware=True,
        match_epoch=datetime(2000, 1, 1),  # Common epoch for historical data
    )
    print(f"Matcher configuration:")
    print(f"  - Positional sigma threshold: {matcher.positional_sigma_threshold}")
    print(f"  - Confidence threshold: {matcher.confidence_threshold}")
    print(f"  - Prior match prob: {matcher.prior_match_prob}")
    print(f"  - Proper motion aware: {matcher.proper_motion_aware}")
    print(f"  - Match epoch: {matcher.match_epoch.isoformat()}")
    
    orchestrator = AstroBridgeOrchestrator(
        router=None,  # Explicit catalogs
        matcher=matcher,
        connectors={"gaia": GaiaAdapter()},
    )
    
    # Load historical catalog
    hist_sources = load_historical_catalog("historical_1995.csv")
    print(f"\nLoaded {len(hist_sources)} historical sources")
    
    # Query Gaia for same regions
    gaia_sources = []
    for source in hist_sources:
        request = QueryRequest(
            query_type="coordinates",
            ra=source.coordinate.ra,
            dec=source.coordinate.dec,
            search_radius_arcsec=60,
            catalogs=["gaia"],
        )
        response = await orchestrator.execute_query(request)
        gaia_sources.extend(response.sources)
    
    print(f"Downloaded {len(gaia_sources)} Gaia sources")
    
    # Cross-match
    matches = matcher.match(hist_sources, gaia_sources)
    print(f"\nFound {len(matches)} matches")
    
    # Analyze results
    confidences = [m.confidence for m in matches]
    print(f"Confidence statistics:")
    print(f"  Mean: {sum(confidences)/len(confidences):.3f}")
    print(f"  Min: {min(confidences):.3f}")
    print(f"  Max: {max(confidences):.3f}")
    
    # Save results with metadata
    save_matches_with_metadata(
        matches, hist_sources, gaia_sources,
        output_file="published_matches.fits",
        header_comments={
            "AUTHOR": "Smith et al.",
            "DATE": datetime.now().isoformat(),
            "MATCHER_VERSION": "BayesianMatcher v0.1",
            "EPOCH": "2000-01-01",
        }
    )
    
    print("\nResults saved to published_matches.fits")
    print("Full audit log in cross_match_study.log")

if __name__ == "__main__":
    asyncio.run(main())
```

### Workflow 2: Educational Lab Assignment

Goal: Students cross-match a small synthetic catalog and analyze confidence scores.

```python
"""
Lab 3: Understanding Bayesian Cross-Matching
Student: Jane Doe
Date: April 2026

In this lab, you'll cross-match two synthetic catalogs and explore how
astrometric and photometric uncertainties affect match confidence.
"""

import asyncio
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.matching import BayesianMatcher, ConfidenceScorer

async def lab_exercise():
    print("=" * 70)
    print("LAB 3: Bayesian Cross-Matching")
    print("=" * 70)
    
    # Part 1: Load synthetic data
    print("\n[Part 1] Load synthetic catalogs")
    catalog_a = load_catalog("synthetic_a.csv")
    catalog_b = load_catalog("synthetic_b.csv")
    print(f"Catalog A: {len(catalog_a)} sources")
    print(f"Catalog B: {len(catalog_b)} sources")
    
    # Part 2: Experiment with different confidence thresholds
    print("\n[Part 2] Sensitivity analysis: confidence threshold")
    thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
    
    results = {}
    for threshold in thresholds:
        matcher = BayesianMatcher(confidence_threshold=threshold)
        matches = matcher.match(catalog_a, catalog_b)
        results[threshold] = len(matches)
        print(f"  Threshold {threshold}: {len(matches)} matches")
    
    # Part 3: Analyze a specific match
    print("\n[Part 3] Detailed analysis of interesting match")
    matcher = BayesianMatcher()
    matches = matcher.match([catalog_a[0]], catalog_b)
    
    if matches:
        match = matches[0]
        print(f"Source A: {catalog_a[0].name}")
        print(f"Source B: {match.source2_id}")
        print(f"Separation: {match.separation_arcsec:.3f} arcsec")
        print(f"Match probability: {match.match_probability:.3f}")
        print(f"Confidence: {match.confidence:.3f}")
    
    # Part 4: Student investigation question
    print("\n[Part 4] Discussion question:")
    print("How would adjusting astrometric_weight affect matches?")
    print("Try it yourself:")
    
    for weight in [0.5, 0.7, 0.9]:
        scorer = ConfidenceScorer(
            astrometric_weight=weight,
            photometric_weight=1-weight,
        )
        print(f"  Astrometric weight {weight}: [implement this yourself]")

asyncio.run(lab_exercise())
```

---

## Visualization & Analysis

### Interactive Match Inspection

```python
import matplotlib.pyplot as plt
import numpy as np

def visualize_matches(
    reference_sources,
    candidate_sources,
    matches,
    markersize=50,
):
    """Visualize matched sources on sky."""
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Plot all sources
    ref_ras = [s.coordinate.ra for s in reference_sources]
    ref_decs = [s.coordinate.dec for s in reference_sources]
    ax.scatter(ref_ras, ref_decs, s=markersize, c='blue', alpha=0.6, label='Reference')
    
    cand_ras = [s.coordinate.ra for s in candidate_sources]
    cand_decs = [s.coordinate.dec for s in candidate_sources]
    ax.scatter(cand_ras, cand_decs, s=markersize, c='red', alpha=0.6, label='Candidates')
    
    # Draw match lines
    for match in matches:
        ref = next(s for s in reference_sources if s.id == match.source1_id)
        cand = next(s for s in candidate_sources if s.id == match.source2_id)
        
        color = 'green' if match.confidence > 0.7 else 'orange'
        alpha = min(1.0, match.confidence)
        
        ax.plot(
            [ref.coordinate.ra, cand.coordinate.ra],
            [ref.coordinate.dec, cand.coordinate.dec],
            c=color, alpha=alpha, linewidth=1,
        )
    
    ax.set_xlabel('RA (deg)')
    ax.set_ylabel('Dec (deg)')
    ax.legend()
    ax.grid()
    plt.show()

# Usage
visualize_matches(gaia_sources, simbad_sources, matches)
```

### Confidence Score Distribution

```python
import matplotlib.pyplot as plt

def plot_confidence_distribution(matches):
    """Histogram of match confidences."""
    
    confidences = [m.confidence for m in matches]
    
    fig, ax = plt.subplots()
    ax.hist(confidences, bins=20, edgecolor='black')
    ax.set_xlabel('Confidence')
    ax.set_ylabel('Number of Matches')
    ax.set_title('Distribution of Match Confidences')
    ax.axvline(0.7, color='red', linestyle='--', label='Threshold')
    ax.legend()
    plt.show()
    
    print(f"Mean confidence: {np.mean(confidences):.3f}")
    print(f"Median confidence: {np.median(confidences):.3f}")
    print(f"High confidence (>0.7): {sum(1 for c in confidences if c > 0.7)}/{len(confidences)}")

plot_confidence_distribution(matches)
```

---

## Teaching with AstroBridge

### Curriculum Integration Ideas

1. **Introductory Astronomy**
   - Demo cli command: "Observe how the same star appears in multiple catalogs"
   - Lab: Use `astrobridge-identify` to classify unknown objects

2. **Observational Astronomy**
   - Build a custom catalog from student observations
   - Cross-match against Gaia to measure uncertainties
   - Analyze confidence scores to understand survey precision

3. **Astrometry & Stellar Kinematics**
   - Deep dive into proper-motion-aware matching
   - Study epoch transformations
   - Build adaptive search radii based on proper motion

4. **Data Science & Machine Learning**
   - Understand Bayesian inference through matching algorithm
   - Explore weighting profiles and their statistical basis
   - Build custom confidence scorers with neural networks (future)

5. **Survey & Big Data**
   - Design efficient catalog adapters
   - Analyze cross-matching performance at scale
   - Build data pipelines with AstroBridge

### Example: 3-Week Lab Module

**Week 1**: Bayesian Fundamentals
- Read [docs/ALGORITHM_AND_SCIENCE.md](../ALGORITHM_AND_SCIENCE.md)
- Run `astrobridge-demo` and trace logic
- Quiz on posterior probability computation

**Week 2**: Hands-On Matching
- Load two synthetic catalogs
- Experiment with confidence thresholds
- Visualize matches on sky
- Write report analyzing a few "interesting" matches

**Week 3**: Integration Project
- Build a custom catalog adapter (CSV, JSON, or REST)
- Integrate it into the orchestrator
- Cross-match against Gaia
- Present findings

---

**Last Updated**: April 2026

For current architecture details, see:
- `astrobridge/api/` — Orchestration
- `astrobridge/matching/` — Matching algorithms
- `astrobridge/routing/` — Catalog selection
- `astrobridge/connectors.py` — Catalog adapters
- `demo.py` — End-to-end example
