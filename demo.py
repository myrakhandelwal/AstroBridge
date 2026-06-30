"""AstroBridge demo — runs fully offline, no network or API keys required.

What this covers
----------------
1. Build a CelestialObject from raw catalog sources (the from_sources() factory)
2. Best-source-per-field synthesis  (Gaia owns position, SIMBAD owns classification)
3. describe() — template-based plain-English summaries for stars, galaxies, unknowns
4. identify_object() — NLP routing that classifies a query and recommends catalogs
5. Offline lookup via local connector fallback
6. Bayesian cross-matching (researcher tool)
7. Full public API surface

Run it
------
    python demo.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from astrobridge.ai_description import generate_description
from astrobridge.identify import identify_object
from astrobridge.models import (
    CelestialObject,
    Coordinate,
    ObjectType,
    Photometry,
    Provenance,
    Source,
    Uncertainty,
)

W = 60
LINE  = "─" * W
THICK = "═" * W


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def make_source(
    catalog: str,
    name: str,
    ra: float,
    dec: float,
    ra_err: float,
    dec_err: float,
    mags: dict,
    obj_type: str,
    parallax: float | None = None,
    redshift: float | None = None,
) -> Source:
    """Build a realistic Source as a TAP adapter would return."""
    return Source(
        id=f"{catalog}:{name}",
        name=name,
        coordinate=Coordinate(ra=ra, dec=dec),
        uncertainty=Uncertainty(ra_error=ra_err, dec_error=dec_err),
        photometry=[Photometry(magnitude=m, band=b) for b, m in mags.items()],
        provenance=Provenance(
            catalog_name=catalog,
            catalog_version="2024",
            query_timestamp=datetime.utcnow(),
            source_id=name,
        ),
        object_type=obj_type,
        parallax_mas=parallax,
        redshift=redshift,
    )


def section(title: str) -> None:
    print(f"\n{THICK}")
    print(f"  {title}")
    print(THICK)


def subsection(title: str) -> None:
    print(f"\n{LINE}")
    print(f"  {title}")
    print(LINE)


# ─────────────────────────────────────────────────────────────
# 1. CelestialObject — build from multi-catalog sources
# ─────────────────────────────────────────────────────────────

section("1 · CelestialObject.from_sources()  — best-field synthesis")

print("""
  Two catalogs see Proxima Centauri:
    SIMBAD   → name + classification (Em*), coarse position (±0.5 mas)
    Gaia DR3 → precise position (±0.02 mas), proper motion, parallax, GBP/GRP
""")

simbad = make_source(
    "SIMBAD", "Proxima Centauri",
    ra=217.429, dec=-62.680,
    ra_err=0.5, dec_err=0.5,
    mags={"V": 11.05, "B": 12.95},
    obj_type="Em*",
)

gaia = make_source(
    "Gaia DR3", "Proxima Centauri",
    ra=217.42895, dec=-62.67948,
    ra_err=0.02, dec_err=0.02,
    mags={"G": 11.13, "BP": 13.02, "RP": 9.55},
    obj_type="star",
    parallax=768.5,
)

proxima = CelestialObject.from_sources([simbad, gaia])

print(f"  primary_name      : {proxima.primary_name}")
print(f"  object_type       : {proxima.object_type.value}  (classification_source={proxima.classification_source!r})")
print(f"  RA / Dec          : {proxima.ra:.5f}  {proxima.dec:.5f}  (position_source={proxima.position_source!r})")
print(f"  parallax          : {proxima.parallax_mas} mas  →  {proxima.distance_pc:.2f} pc  ({proxima.distance_pc * 3.2616:.2f} ly)")
print(f"  photometry        : {proxima.photometry_summary}")
print(f"  catalogs          : {proxima.source_catalogs}")


# ─────────────────────────────────────────────────────────────
# 2. describe() — plain-English summaries
# ─────────────────────────────────────────────────────────────

section("2 · CelestialObject.describe()  — no LLM required")

subsection("2a · Star  (Proxima Centauri)")
print(f"\n  {proxima.describe()}")

subsection("2b · Galaxy  (M31 / Andromeda)")
m31 = CelestialObject(
    primary_name="M31",
    ra=10.6848,
    dec=41.2690,
    object_type=ObjectType.GALAXY,
    redshift=0.000360,
    redshift_type="spectroscopic",
    redshift_source="NED",
    source_catalogs=["NED", "SIMBAD"],
    alternate_names=["Andromeda Galaxy", "NGC 224"],
)
print(f"\n  {m31.describe()}")

subsection("2c · Quasar  (3C 273)")
qso = CelestialObject(
    primary_name="3C 273",
    ra=187.2779,
    dec=2.0523,
    object_type=ObjectType.QUASAR,
    redshift=0.158,
    redshift_type="spectroscopic",
    source_catalogs=["NED", "SDSS"],
)
print(f"\n  {qso.describe()}")

subsection("2d · Unknown / unclassified object")
mystery = CelestialObject(primary_name="J123456.7+654321", ra=188.736, dec=65.722)
print(f"\n  {mystery.describe()}")


# ─────────────────────────────────────────────────────────────
# 3. AI description stub (no API key needed in stub mode)
# ─────────────────────────────────────────────────────────────

section("3 · AI description  (stub — set AI_PROVIDER=anthropic to go live)")

os.environ.setdefault("AI_PROVIDER", "stub")

desc = generate_description(proxima, conn=None)
print(f"\n  {desc}")
print(
    "\n  Tip: set AI_PROVIDER=anthropic and AI_API_KEY=<key> for a real"
    "\n  Claude-generated paragraph instead of the stub placeholder."
)


# ─────────────────────────────────────────────────────────────
# 4. identify_object() — NLP routing, no network
# ─────────────────────────────────────────────────────────────

section("4 · identify_object()  — NLP routing (offline)")

queries = [
    "M31",
    "Proxima Centauri",
    "Sirius",
    "Crab Nebula supernova remnant",
    "red dwarf stars in solar neighborhood",
    "gravitational lensing quasar",
    "open cluster near the Orion arm",
    "3C 273",
]

radius_hdr = 'Radius"'
print(f"\n  {'Query':<42} {'Class':<10} {'Top catalogs':<22} {radius_hdr}")
print(f"  {'─'*42} {'─'*10} {'─'*22} {'─'*7}")
for q in queries:
    r = identify_object(q)
    top2 = ", ".join(r.top_catalogs[:2])
    print(f"  {q:<42} {r.object_class.value:<10} {top2:<22} {r.search_radius_arcsec:.0f}")


# ─────────────────────────────────────────────────────────────
# 5. Offline lookup (local connectors, no pyvo needed)
# ─────────────────────────────────────────────────────────────

section("5 · lookup_object()  — offline mode (local connector fallback)")

async def demo_lookup() -> None:
    from astrobridge.lookup import lookup_object, lookup_by_coordinates

    obj = await lookup_object("Proxima Centauri", live=False)
    if obj:
        print(f"\n  lookup_object('Proxima Centauri')")
        print(f"    name     : {obj.primary_name}")
        print(f"    type     : {obj.object_type.value}")
        print(f"    RA / Dec : {obj.ra:.3f}  {obj.dec:.3f}")
    else:
        print("\n  (no local result — install pyvo for live queries)")

    results = await lookup_by_coordinates(217.429, -62.680, radius_arcsec=120, live=False)
    print(f"\n  lookup_by_coordinates(217.43, -62.68, 120\")  →  {len(results)} object(s) found")
    for r in results:
        print(f"    {r.primary_name:<28}  RA={r.ra:.3f}  Dec={r.dec:.3f}")

asyncio.run(demo_lookup())


# ─────────────────────────────────────────────────────────────
# 6. Bayesian cross-matching (researcher tool)
# ─────────────────────────────────────────────────────────────

section("6 · BayesianMatcher  — probabilistic cross-matching")

from astrobridge.matching import BayesianMatcher

ref_sources = [
    make_source("SIMBAD", "Proxima Centauri", 217.42895, -62.67948, 0.5, 0.5, {"V": 11.05}, "Em*"),
    make_source("SIMBAD", "Barnard's Star",   269.45208,   4.69339, 0.5, 0.5, {"V":  9.54}, "star"),
    make_source("SIMBAD", "Wolf 359",         164.12033,   7.00590, 0.5, 0.5, {"V": 13.44}, "star"),
]

cand_sources = [
    make_source("Gaia DR3", "source_A",  217.42898, -62.67951, 0.02, 0.02, {"G": 11.13}, "star"),
    make_source("Gaia DR3", "source_B",  269.45210,   4.69341, 0.02, 0.02, {"G":  9.51}, "star"),
    make_source("Gaia DR3", "source_C",  164.12037,   7.00591, 0.02, 0.02, {"G": 13.40}, "star"),
    make_source("Gaia DR3", "unrelated",  45.0,       30.0,    0.02, 0.02, {"G": 15.00}, "star"),
]

matcher = BayesianMatcher(proper_motion_aware=False)
matches = matcher.match(ref_sources, cand_sources)

print(f"\n  {len(ref_sources)} SIMBAD sources × {len(cand_sources)} Gaia sources  →  {len(matches)} match(es)\n")
sep_hdr = 'sep"'
print(f"  {'Ref':<24} {'Candidate':<16} {'p':>6}  {sep_hdr:>6}")
print(f"  {'─'*24} {'─'*16} {'─'*6}  {'─'*6}")
for m in sorted(matches, key=lambda x: -x.match_probability):
    print(f"  {m.source1_id:<24} {m.source2_id:<16} {m.match_probability:>6.3f}  {m.separation_arcsec:>6.3f}")


# ─────────────────────────────────────────────────────────────
# 7. Public API surface
# ─────────────────────────────────────────────────────────────

section("7 · Public API  (import astrobridge)")

import astrobridge

print(f"\n  version : {astrobridge.__version__}\n")
for name in astrobridge.__all__:
    attr = getattr(astrobridge, name)
    kind = type(attr).__name__
    print(f"  astrobridge.{name:<22}  [{kind}]")

print(f"\n{THICK}")
print("  Demo complete — all sections passed ✓")
print(THICK + "\n")
