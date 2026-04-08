# AstroBridge Platforms and Catalog Matrix

## Scope

This document lists catalogs and platforms relevant to the current AstroBridge pipeline, including what object types they are best suited for.

## 1) Catalogs in AstroBridge Routing Layer

| Catalog | Primary Object Coverage | Typical Use in Pipeline | Notes |
|---|---|---|---|
| SIMBAD | Stars, nebulae, mixed named objects | Name resolution and broad object lookup | General-purpose astronomical database |
| NED | Galaxies, AGN, quasars, extragalactic objects | Extragalactic cross-checks and object metadata | Extragalactic focus |
| Gaia | Stars, clusters, stellar astrometry | High-precision positional anchoring | Strong astrometric reference catalog |
| SDSS | Galaxies, quasars, stars (survey regions) | Optical photometric comparison | Survey footprint constrained |
| WISE | IR-bright sources, AGN candidates, dusty objects | Infrared property checks | Useful for IR emphasis in routing |
| Pan-STARRS | Stars, galaxies, transients in survey coverage | Multi-epoch optical augmentation | Good wide-field optical support |
| ZTF | Transients, variable stars, supernovae | Variability and transient-focused workflows | Time-domain oriented |
| ATLAS | Survey and transient support targets | Supplemental routing option | Catalog utility depends on target class |

## 2) Connectors Implemented in AstroBridge

| Connector/Class | Type | Object Types | Status |
|---|---|---|---|
| SimbadConnector | Deterministic/local connector | General objects; star-centric examples | Implemented and tested |
| NEDConnector | Deterministic/local connector | Extragalactic examples | Implemented and tested |
| SimbadTapAdapter | Live TAP adapter | SIMBAD-served objects | Implemented (requires live deps) |
| NedTapAdapter | Live TAP adapter | NED-served extragalactic objects | Implemented (requires live deps) |

## 3) Object Classes in AstroBridge Routing

| Object Class | Typical Catalog Preference |
|---|---|
| STAR | Gaia, SIMBAD, SDSS/Pan-STARRS |
| GALAXY | NED, SDSS, WISE |
| QUASAR | NED, SDSS, WISE, ZTF |
| AGN | NED, WISE, SDSS |
| NEBULA | SIMBAD, Pan-STARRS, WISE |
| CLUSTER | Gaia, SIMBAD, SDSS/Pan-STARRS |
| SNE | ZTF, Pan-STARRS, SDSS |
| UNKNOWN | Mixed default ranking from router |

## 4) External Platforms Frequently Paired With This Workflow

| Platform/Survey | Best For | Pipeline Role |
|---|---|---|
| Gaia | Stellar astrometry and proper motion | Positional reference and match constraints |
| SIMBAD | Named object lookup and object metadata | Initial object grounding |
| NED | Extragalactic identification | Galaxy/AGN/quasar enrichment |
| SDSS | Optical photometry/spectroscopic context | Cross-catalog photometric comparison |
| WISE | Infrared source characterization | IR routing and photometric signals |
| Pan-STARRS | Wide-field optical imaging | Supplemental detection and photometry |
| ZTF | Variability and transient detection | Time-domain and event-driven workflows |

## 5) Selection Guidance

- For nearby stars and precision matching: prioritize Gaia and SIMBAD.
- For galaxy and AGN workflows: prioritize NED, then SDSS/WISE.
- For transients or supernova-like behavior: prioritize ZTF and Pan-STARRS.
- For uncertain target class: use natural-language routing and inspect top-ranked catalogs before batch execution.
