# AstroBridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/myrakhandelwal/AstroBridge/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Status: Stable](https://img.shields.io/badge/status-stable-green.svg)](https://github.com/myrakhandelwal/AstroBridge)
[![GitHub](https://img.shields.io/badge/github-myrakhandelwal%2FAstroBridge-blue.svg)](https://github.com/myrakhandelwal/AstroBridge)

**Version 1.0.0** — Unified astronomical object lookup across SIMBAD, NED, Gaia DR3, and 2MASS.

AstroBridge is a Python library that lets you look up any astronomical object by name or coordinates, merge data from multiple catalogs into a single clean `CelestialObject`, and get plain-English descriptions — no LLM API key required for basic use.

```python
import asyncio
import astrobridge

async def main():
    obj = await astrobridge.lookup("Proxima Centauri")
    print(obj.describe())
    # Proxima Centauri is a star (Em*). It lies 1.30 parsecs (4.24 light-years)
    # from Earth. Brightness: G=11.1, V=11.1 (magnitudes). Data sourced from
    # SIMBAD, Gaia DR3.

asyncio.run(main())
```

---

## Install

```bash
git clone https://github.com/myrakhandelwal/AstroBridge.git
cd AstroBridge
python -m venv .venv && source .venv/bin/activate

pip install -e .           # core (no network queries)
pip install -e .[live]     # + live TAP queries to SIMBAD, NED, Gaia DR3, 2MASS
pip install -e .[dev]      # + pytest, mypy, ruff
```

Live queries require `pyvo`. Without it, AstroBridge falls back to built-in local datasets automatically — all tests and the demo run offline.

---

## Quick Start

```bash
# Full offline demo (no network, no API keys)
python demo.py

# Identify an object and get catalog recommendations
astrobridge-identify "Proxima Centauri"
astrobridge-identify "Find nearby red dwarf stars" --json
```

---

## Core Concept: CelestialObject

`CelestialObject` is the single unified model at the center of AstroBridge. It holds the best available data across all catalogs you query:

| Field | Best source |
|-------|-------------|
| `ra`, `dec`, `position_error_arcsec` | Gaia DR3 > 2MASS > NED > SIMBAD |
| `parallax_mas`, `distance_pc` | Gaia DR3 only |
| `redshift`, `redshift_type` | NED > SDSS |
| `object_type`, `raw_classification` | SIMBAD > NED |
| `photometry_summary` | merged from all catalogs |

```python
from astrobridge.models import CelestialObject, Source, ObjectType

# Build from raw catalog sources (what the live adapters return)
obj = CelestialObject.from_sources([simbad_source, gaia_source])

print(obj.primary_name)          # Proxima Centauri
print(obj.object_type)           # ObjectType.STAR
print(obj.ra, obj.dec)           # 217.42895  -62.67948  (Gaia DR3 wins)
print(obj.position_source)       # 'Gaia DR3'
print(obj.parallax_mas)          # 768.5
print(obj.distance_pc)           # 1.30
print(obj.photometry_summary)    # {'V': 11.05, 'G': 11.13, 'BP': 13.02, 'RP': 9.55}
print(obj.source_catalogs)       # ['SIMBAD', 'Gaia DR3']
```

---

## describe() — Plain-English Summaries

Every `CelestialObject` can describe itself without any LLM:

```python
# Star with parallax
proxima.describe()
# "Proxima Centauri is a star (Em*). It lies 1.30 parsecs (4.24 light-years)
#  from Earth. Brightness: G=11.1, V=11.1 (magnitudes). Data sourced from
#  SIMBAD, Gaia DR3."

# Galaxy with redshift
m31.describe()
# "M31 is a galaxy. It has a redshift of z = 0.0004, placing it approximately
#  2 Mpc from Earth. Data sourced from NED, SIMBAD."

# Quasar
qso_3c273.describe()
# "3C 273 is a quasar. It has a redshift of z = 0.1580, placing it
#  approximately 677 Mpc from Earth. Data sourced from NED, SDSS."
```

To get an LLM-generated paragraph instead, set `AI_PROVIDER`:

```bash
export AI_PROVIDER=anthropic
export AI_API_KEY=sk-ant-...
```

```python
from astrobridge.ai_description import generate_description
print(generate_description(obj))   # calls Claude; falls back to template if unconfigured
```

Supported providers: `anthropic`, `openai`, `local` (OpenAI-compatible), `stub` (default, no key needed).

---

## Live Catalog Lookup

Requires `pip install -e .[live]`. Falls back to local connectors automatically.

```python
import asyncio
import astrobridge

async def main():
    # Name lookup — fans out to SIMBAD + NED, then enriches with Gaia DR3 + 2MASS
    obj = await astrobridge.lookup("M31")
    print(obj.describe())

    # Cone search — returns one CelestialObject per distinct sky position
    results = await astrobridge.search(ra=10.68, dec=41.27, radius_arcsec=120)
    for r in results:
        print(r.primary_name, r.ra, r.dec)

    # Natural-language query (short inputs → direct lookup; longer → NLP-routed)
    results = await astrobridge.query("Andromeda Galaxy")

asyncio.run(main())
```

The two-step lookup strategy:
1. **Name resolution** — SIMBAD and NED queried concurrently (both support object names)
2. **Positional enrichment** — returned coordinates used to cone-search Gaia DR3 and 2MASS

---

## Object Identification (NLP Routing)

Classify a query and get catalog recommendations — no network needed:

```python
from astrobridge.identify import identify_object

r = identify_object("Find high-redshift quasars")
print(r.object_class)             # ObjectClass.QUASAR
print(r.top_catalogs)             # ['NED', 'SDSS', 'ALLWISE']
print(r.search_radius_arcsec)     # 10.0
print(r.reasoning)                # "Quasar / AGN keywords detected..."
```

```bash
# CLI
astrobridge-identify "Betelgeuse"
astrobridge-identify "Crab Nebula supernova remnant" --json
```

---

## Bayesian Cross-Matching

For researchers who need to cross-identify sources between catalogs:

```python
from astrobridge.matching import BayesianMatcher

matcher = BayesianMatcher(proper_motion_aware=True)
matches = matcher.match(reference_sources, candidate_sources)

for m in matches:
    print(f"{m.source1_id} ↔ {m.source2_id}  p={m.match_probability:.3f}  sep={m.separation_arcsec:.2f}\"")
```

The matcher uses Bayesian posterior probabilities combining positional separation and photometric similarity, with optional proper-motion corrections across epochs.

---

## Supported Catalogs

| Catalog | Adapter | Name lookup | Cone search | Best for |
|---------|---------|-------------|-------------|----------|
| SIMBAD | `SimbadTapAdapter` | ✅ | ✅ | All objects, name resolution, classification |
| NED | `NedTapAdapter` | ✅ | ✅ | Galaxies, AGN, quasars, redshifts |
| Gaia DR3 | `GaiaDR3TapAdapter` | — | ✅ | Stars: astrometry, proper motions, parallax |
| 2MASS | `TwoMassTapAdapter` | — | ✅ | Stars + galaxies: J/H/Ks photometry |
| SDSS | routing only | | | Galaxies, QSOs, optical photometry |
| WISE / AllWISE | routing only | | | Mid-IR sources, AGN |
| PanSTARRS | routing only | | | Wide-field optical, transients |
| ZTF | routing only | | | Supernovae, variables, transients |
| ATLAS | routing only | | | Transient alerts |
| Hipparcos | routing only | | | Bright stars (V < 12) |
| VizieR | routing only | | | Any published catalog table |
| NASA Exoplanet Archive | routing only | | | Exoplanet host stars |

"Routing only" means AstroBridge's NLP router knows which catalog to recommend for a given query type, but does not yet have a live TAP adapter for it.

---

## Public API

```python
import astrobridge

astrobridge.lookup(name, ...)          # async — name → CelestialObject
astrobridge.search(ra, dec, r, ...)    # async — cone → list[CelestialObject]
astrobridge.query(description, ...)    # async — natural language → list[CelestialObject]
astrobridge.identify(text)             # sync  — NLP classification (no network)
astrobridge.BayesianMatcher            # probabilistic cross-matching
astrobridge.NLPQueryRouter             # query classification and catalog ranking

# Models
astrobridge.CelestialObject            # unified object (core model)
astrobridge.Source                     # single-catalog raw record
astrobridge.ObjectType                 # enum: STAR, GALAXY, QUASAR, AGN, NEBULA, CLUSTER, SNE, UNKNOWN
astrobridge.Coordinate                 # ra, dec, pm_ra, pm_dec
astrobridge.Uncertainty                # ra_error, dec_error
astrobridge.Photometry                 # magnitude + band
astrobridge.Provenance                 # catalog_name, query_timestamp, source_id
astrobridge.MatchResult                # cross-match result with probability + separation
```

---

## Project Layout

```
astrobridge/
├── models.py           # CelestialObject, Source, Coordinate, ObjectType, MatchResult
├── lookup.py           # lookup_object(), lookup_by_coordinates() — live two-step fan-out
├── identify.py         # identify_object(), identify_from_catalogs() — NLP + live lookup
├── connectors.py       # SimbadTapAdapter, NedTapAdapter, GaiaDR3TapAdapter, TwoMassTapAdapter
├── ai_description.py   # generate_description() — anthropic / openai / local / stub
├── geometry.py         # angular_distance_arcsec()
├── routing/            # NLPQueryRouter, CatalogRanker, 13 CatalogTypes
└── matching/           # BayesianMatcher, ConfidenceScorer, SpatialIndex
```

---

## Quality Gates

```bash
ruff check .           # linting
mypy astrobridge/      # type checking
pytest -q              # 163 tests, zero failures
```

---

## Release History

| Tag | Date | Highlights |
|-----|------|------------|
| `v1.0.0` | Jun 2026 | CelestialObject model, best-source synthesis, describe(), scope cleanup |
| `v0.3.3` | Apr 2026 | Live catalog adapters, Gaia DR3 + 2MASS, AI descriptions |
| `v0.3.0` | Apr 2026 | PEP 621 packaging, ruff, async concurrency |
| `v0.1.1` | — | Initial release |

---

## License

MIT License — Copyright © 2026 Myra Khandelwal

All tests and `demo.py` run fully offline — no network access or API keys required.
