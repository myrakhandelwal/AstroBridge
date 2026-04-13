# AstroBridge Platforms and Catalog Matrix

## Scope

This document lists all catalogs in the AstroBridge pipeline, including live adapter status, object type coverage, and routing priority guidance.

## 1) Catalogs in AstroBridge Routing Layer

| Catalog | Live Adapter | Primary Object Coverage | Notes |
|---------|-------------|------------------------|-------|
| SIMBAD | ✅ `SimbadTapAdapter` | Stars, nebulae, all named objects | General-purpose; best for name lookup |
| NED | ✅ `NedTapAdapter` | Galaxies, AGN, quasars, extragalactic | Best for extragalactic objects |
| Gaia DR3 | ✅ `GaiaDR3TapAdapter` | Stars, clusters — cone search only | Best astrometry + proper motions + parallax |
| 2MASS | ✅ `TwoMassTapAdapter` | Stars, galaxies — cone search only | J/H/Ks near-IR photometry (IRSA TAP) |
| SDSS | routing only | Galaxies, quasars, stars (survey area) | Survey footprint constrained |
| WISE | routing only | IR-bright sources, AGN, dusty objects | Mid-IR 3.4–22 µm |
| AllWISE | routing only | All WISE sources + proper motions | Improved over WISE alone |
| PanSTARRS | routing only | Stars, galaxies, transients | Wide-field optical 3π survey |
| ZTF | routing only | Transients, variables, supernovae | Time-domain / alert stream |
| ATLAS | routing only | Transients, SNe | Alert stream |
| Hipparcos | routing only | Bright stars (V < 12) | Superseded by Gaia; useful for bright reference |
| VizieR | routing only | All published catalog tables | Gateway to thousands of sub-catalogs |
| NASA Exoplanet Archive | routing only | Exoplanet host stars | TESS/Kepler/RV confirmed planets |

## 2) Live Adapters

| Connector Class | Catalog | Name Lookup | Cone Search | TAP Endpoint |
|----------------|---------|-------------|-------------|--------------|
| `SimbadConnector` | SIMBAD (local) | ✅ (6 objects) | ✅ | Built-in (no network) |
| `NEDConnector` | NED (local) | ✅ (6 objects) | ✅ | Built-in (no network) |
| `SimbadTapAdapter` | CDS SIMBAD | ✅ | ✅ | `simbad.cds.unistra.fr/simbad/sim-tap` |
| `NedTapAdapter` | NASA NED | ✅ | ✅ | `ned.ipac.caltech.edu/tap` |
| `GaiaDR3TapAdapter` | ESA Gaia DR3 | — | ✅ | `gea.esac.esa.int/tap-server/tap` |
| `TwoMassTapAdapter` | 2MASS/IRSA | — | ✅ | `irsa.ipac.caltech.edu/TAP` |

**Note**: Gaia DR3 and 2MASS do not expose a human-readable name index. `lookup_object()` uses a two-step strategy: SIMBAD/NED resolve the name → coordinates → Gaia + 2MASS enrich with cone searches.

## 3) Object Classes and Catalog Routing Priorities

| Object Class | Top Catalogs (score) |
|---|---|
| STAR | Gaia (0.95), SIMBAD (0.90), Hipparcos (0.85), 2MASS (0.80), SDSS (0.75) |
| GALAXY | NED (0.95), SDSS (0.85), AllWISE (0.78), WISE (0.75), SIMBAD (0.70) |
| QUASAR | NED (0.90), SDSS (0.85), AllWISE (0.82), WISE (0.80), ZTF (0.70) |
| AGN | NED (0.92), AllWISE (0.90), WISE (0.88), SDSS (0.80), ZTF (0.75) |
| NEBULA | SIMBAD (0.90), PanSTARRS (0.75), WISE (0.70), SDSS (0.60), 2MASS (0.55) |
| CLUSTER | Gaia (0.95), SIMBAD (0.85), Hipparcos (0.75), PanSTARRS (0.75), 2MASS (0.70) |
| SNE | ZTF (0.95), PanSTARRS (0.85), ATLAS (0.80), SIMBAD (0.60), NED (0.55) |
| UNKNOWN | SIMBAD (0.80), Gaia (0.75), NED (0.70), VizieR (0.60), SDSS (0.65) |

## 4) Property Modifiers (applied on top of base scores)

| Property keyword | Catalogs boosted |
|---|---|
| `infrared`, `ir`, `wise` | WISE +0.15, AllWISE +0.15, 2MASS +0.10 |
| `2mass`, `j-band`, `nir` | 2MASS +0.20, AllWISE +0.10 |
| `exoplanet`, `planet`, `tess` | Exoplanet Archive +0.40, Gaia +0.10 |
| `nearby`, `local`, `within 100 pc` | Gaia +0.15, Hipparcos +0.15 |
| `bright`, `mag < 10` | Hipparcos +0.15, Gaia +0.10, SIMBAD +0.10 |
| `variable`, `transient` | ZTF +0.20, ATLAS +0.15, PanSTARRS +0.10 |
| `high redshift`, `distant` | NED +0.15, SDSS +0.10 |
| `radio` | NED +0.15, VizieR +0.10 |

## 5) Selection Guidance

- **Stellar astrometry / proper motions**: Gaia DR3 (best available) + Hipparcos for bright stars
- **Nearby objects, exoplanet hosts**: Gaia DR3 + 2MASS + Exoplanet Archive
- **Near-infrared photometry**: 2MASS (J/H/Ks) + AllWISE (W1/W2)
- **Galaxy / AGN / quasar**: NED first, then SDSS + AllWISE
- **Transients / supernovae**: ZTF + PanSTARRS + ATLAS
- **General unknown targets**: SIMBAD + NED (both support name lookup)
- **Accessing any published catalog table**: VizieR (routing priority; adapter planned)
