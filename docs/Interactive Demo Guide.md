# AstroBridge Interactive Live Demo Guide

**Version**: v0.3.0  
**Location**: `interactive_demo.py` or `astrobridge-interactive` command  
**Purpose**: Hands-on exploration of AstroBridge with live user input

---

## Quick Start

### Installation

```bash
# Install with interactive demo support
pip install -e .

# Or with all extras (live TAP adapters, web UI)
pip install -e .[dev,live,web]
```

### Running the Demo

```bash
# Method 1: Direct script
python interactive_demo.py

# Method 2: Console entry point
astrobridge-interactive

# Method 3: Module import
python -m interactive_demo
```

### First Time Setup

```
🔭 AstroBridge Interactive Demo
Starting live demo...

==============================================================================
  AstroBridge Interactive Live Demo v0.3.0
==============================================================================

Initializing orchestrator...
✓ Live TAP adapters available
✓ Orchestrator ready

==============================================================================
  MAIN MENU
==============================================================================

1. Query by object name
2. Query by coordinates (cone search)
3. Natural language query
4. Object identification
5. Advanced matcher controls
6. Performance benchmarking
7. Exit

Select option (1-7): 
```

Choose **option 1** for your first demo.

---

## Menu Options Explained

### 1. Query by Object Name

**What it does**: Search for a specific astronomical object by name and cross-reference it across multiple catalogs.

**Example usage**:
```
Enter object name (e.g., 'Proxima Centauri', 'M31', 'Sirius'): Sirius
```

**Output**:
```
==============================================================================
  QUERY BY OBJECT NAME
==============================================================================

Querying for: Sirius

------
Results
------
Status: success
Execution time: 125.34ms
Catalogs queried: simbad, ned
Sources found: 2
Matches found: 1

------
Sources
------

1. Sirius A
   Position: RA=101.2865°, Dec=-16.7161°
   Magnitudes: V=1.42, B=0.01
   Source: SIMBAD

2. Sirius
   Position: RA=101.2869°, Dec=-16.7155°
   Magnitudes: V=1.46, B=0.02
   Source: NED

------
Cross-Matches
------

1. Sirius A ↔ Sirius
   Probability: 0.9823
   Separation: 21.45″
   Confidence: 0.9712
```

**When to use it**:
- You know the exact name of the object
- You want to see how multiple catalogs represent the same object
- You're testing matcher confidence scores

**Tips**:
- Try well-known objects first: Proxima Centauri, M31, Vega, etc.
- The demo includes hardcoded data for Proxima Centauri for testing
- Install `[live]` extra for access to real SIMBAD/NED via TAP

---

### 2. Query by Coordinates (Cone Search)

**What it does**: Find all sources within a specified radius around a celestial position.

**Example usage**:
```
Enter celestial coordinates for cone search:
  RA (degrees, 0-360): 217.429
  Dec (degrees, -90 to 90): -62.680
  Search radius (arcseconds, default 60): 120
```

**Output**:
```
==============================================================================
  QUERY BY COORDINATES
==============================================================================

Querying cone: RA=217.429°, Dec=-62.680°, Radius=120″

------
Results
------
Status: success
Execution time: 89.23ms
Sources found: 5
Matches found: 2

------
Sources in cone
------

1. Proxima Centauri
   Position: RA=217.4294°, Dec=-62.6805°
   Separation from query: 2.34″
   Source: SIMBAD

2. Alpha Centauri A
   Position: RA=219.9015°, Dec=-60.8369°
   Separation from query: 125.67″
   Source: SIMBAD
   
... (more sources)
```

**When to use it**:
- You have a position (RA/Dec) and want to find nearby objects
- You're testing cone search radius sensitivity
- You're building a cross-match sample around a specific field

**Tips**:
- RA: 0-360° (hours × 15)
- Dec: -90 to +90°
- Start with radius=60″ (1 arcmin) for tight searches
- Use radius=300″+ for wide-field surveys

**Example coordinates**:
- Proxima Centauri: RA=217.429, Dec=-62.680
- M31 (Andromeda): RA=10.685, Dec=41.269
- Vega: RA=279.235, Dec=38.783

---

### 3. Natural Language Query

**What it does**: Describe what you're looking for in natural language, and AstroBridge routes to the best catalogs automatically.

**Example usage**:
```
Describe what you're looking for (e.g., 'Find nearby red dwarf stars'):
Find faint galaxies in the infrared
```

**Output**:
```
==============================================================================
  NATURAL LANGUAGE QUERY
==============================================================================

Query: Find faint galaxies in the infrared

------
Routing Analysis
------
Routing reasoning:
Detected keywords 'faint', 'galaxies', 'infrared' as object type GALAXY...
Best initial catalog by object type: NED (score: 0.95)
Recommending catalog sequence: NED, PANSTARRS, SDSS

Catalogs selected: ned, simbad, panstarrs

------
Results
------
Status: success
Execution time: 156.42ms
Sources found: 8
Matches found: 3
```

**When to use it**:
- You don't know exact object names
- You want to test the intelligent router
- You're exploring what catalogs work best for different object types

**Example queries**:
- "Find nearby red dwarf stars"
- "Show me galaxies with active nuclei"
- "I want to see quasars in the radio band"
- "Find binary stars"
- "Show nearby supergiants"

**How the router works**:
1. Analyzes query text for object type keywords (star, galaxy, quasar, etc.)
2. Classifies the object type
3. Recommends optimal catalog sequence based on object type
4. Queries selected catalogs and returns unified results

---

### 4. Object Identification

**What it does**: Classify an object and get recommended catalogs, search radius, and description.

**Example usage**:
```
Enter an object name or description (e.g., 'M31', 'a red dwarf'): M31
```

**Output**:
```
==============================================================================
  OBJECT IDENTIFICATION
==============================================================================

Identifying: M31

------
Identification Result
------
Input: M31
Class: galaxy
Description: This looks like a galaxy: an extended extragalactic system containing 
many stars, gas, and dust. M31 is the Andromeda Galaxy, a nearby spiral galaxy in 
the Local Group.
Recommended search radius: 30.0 arcsec
Top catalogs: GAIA, PANSTARRS, SDSS
Reasoning: Recognized M31 as a known galaxy target from a built-in designation hint.
```

**When to use it**:
- You want to understand what AstroBridge thinks your query is
- You need suggested search radius and best catalogs
- You're verifying router classification

**Example inputs**:
- Messier objects: M1, M31, M51, M87
- Named stars: Sirius, Vega, Betelgeuse
- Object types: "a red giant", "a galaxy cluster", "a planetary nebula"

---

### 5. Advanced Matcher Controls

**What it does**: Test how different confidence weighting profiles affect matching results.

**Example usage**:
```
Enter object name for cross-match testing: Sirius
```

**Output**:
```
==============================================================================
  ADVANCED MATCHER CONTROLS
==============================================================================

Query: Sirius

Testing different weighting profiles:

BALANCED:
  Matches found: 1
  Top match confidence: 0.9712

POSITION_FIRST:
  Matches found: 1
  Top match confidence: 0.9845

PHOTOMETRY_FIRST:
  Matches found: 1
  Top match confidence: 0.8934
```

**Weighting Profiles**:

1. **Balanced** (default)
   - Equal weight to astrometric and photometric evidence
   - Best for general cross-matching
   - Confidence = 0.5 × astrometric + 0.5 × photometric

2. **Position First**
   - Prioritizes positional agreement over photometry
   - Use for precise astrometry catalogs (Gaia)
   - Confidence = 0.8 × astrometric + 0.2 × photometric

3. **Photometry First**
   - Prioritizes magnitude/color matching
   - Use for magnitude-limited surveys
   - Confidence = 0.2 × astrometric + 0.8 × photometric

**When to use it**:
- You want to understand how matching algorithms weight evidence
- You're tuning confidence thresholds for your use case
- You're researching astrometric vs. photometric matching trade-offs

---

### 6. Performance Benchmarking

**What it does**: Run multiple queries and measure latency statistics.

**Example usage**:
```
This will run multiple queries and measure latency.
Number of iterations (default 3): 5
```

**Output**:
```
==============================================================================
  PERFORMANCE BENCHMARKING
==============================================================================

Running benchmark with 5 iterations...

------
Benchmark Results
------
Total queries: 5
Successful: 5
Failed: 0

Latency Statistics:
  Mean: 142.35ms
  Median (P50): 138.42ms
  P95: 156.78ms
  Max: 163.21ms
```

**When to use it**:
- You want to evaluate query performance
- You're tuning concurrency (semaphore limits)
- You're comparing live vs. local adapters
- You're stress-testing the orchestrator

**Interpreting results**:
- **Mean**: Average latency across all queries
- **P50 (Median)**: 50th percentile; typical query time
- **P95**: 95th percentile; slow-but-normal queries
- **Max**: Worst-case latency (usually first query, warm-up)

**Tips for benchmarking**:
- Run 5-10 iterations for stable results
- First iteration is usually slower (warm-up)
- Use local connectors for reproducible results
- Use live TAP adapters to test real network latency

---

### 7. Exit

Cleanly exit the interactive demo.

---

## Advanced Usage

### Using with Live TAP Adapters

If you install the `[live]` extra, the demo automatically uses real SIMBAD and NED:

```bash
pip install -e .[live]
python interactive_demo.py
```

You'll see:
```
✓ Live TAP adapters available
✓ Orchestrator ready
```

### Using with Local/Hardcoded Data

Without the `[live]` extra, the demo falls back to synthetic data:

```bash
pip install -e .
python interactive_demo.py
```

You'll see:
```
⚠ Live TAP adapters not available (install [live])
  Using local synthetic connectors...
✓ Orchestrator ready
```

**Note**: Hardcoded data is limited to "Proxima Centauri". Other queries return empty results to avoid confusion.

### Combining Queries

The interactive demo maintains state; you can:
1. Run a name query
2. View the matches
3. Try the same object with different weighting profiles
4. Run benchmarks across all queries

---

## Troubleshooting

### "Live TAP adapters not available"

**Solution**: Install the `[live]` extra:
```bash
pip install -e .[live]
```

Requires `pyvo` and `requests` (for TAP service access).

### "Error: Invalid input"

**Solution**: Check the input format:
- RA must be 0-360°
- Dec must be -90 to +90°
- Radius must be positive number (arcseconds)

### "Query returned empty results"

**Reason**: 
- Using local connectors (no `[live]`) and not searching for "Proxima Centauri"
- Coordinate search radius too small

**Solution**:
- Install `[live]` for real catalog access
- Increase search radius
- Try well-known object names

### "TypeError: object NoneType..."

**Reason**: Missing dependencies or incomplete installation

**Solution**:
```bash
pip install -e .[dev,live,web]
pytest  # Verify installation
```

---

## Example Sessions

### Session 1: Learning Query Types (15 min)

1. Run option 1: Query "Proxima Centauri"
2. Run option 3: Query "Find nearby stars"
3. Run option 4: Identify "M31"
4. Compare results

### Session 2: Testing Matchers (20 min)

1. Run option 1: Query "Sirius"
2. Run option 5: Test weighting profiles
3. Note how confidence changes
4. Run option 6: Benchmark

### Session 3: Coordinates & Cone Search (15 min)

1. Get coordinates from option 4 identification
2. Run option 2 with those coordinates
3. Try different search radii
4. Compare results

---

## Tips & Best Practices

1. **Start simple**: Begin with option 1 (name query) on well-known objects
2. **Verify results**: Cross-check matches across 2-3 objects
3. **Try edge cases**: "Not a star", "binary system", etc. (for router testing)
4. **Monitor latency**: Use option 6 to benchmark your setup
5. **Explore profiles**: Use option 5 to understand matcher behavior
6. **Iterate**: Run the same query multiple times; latency varies

---

## What's Next?

After exploring the interactive demo, check out:
- [Deployment Guide](Deployment%20Guide.md) — Run AstroBridge in production
- [Example Usage](Example%20Usage.md) — Python API patterns
- [Architecture Guide](Architecture%20Guide.md) — Deep dive into design
- [Future Improvements](Future%20Improvements.md) — Planned enhancements

---

**Questions?** Check the main README or API documentation.
