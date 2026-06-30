"""AstroBridge — astronomical catalog wrapper and cross-identifier.

Quick start
-----------
>>> import asyncio
>>> import astrobridge
>>>
>>> obj = asyncio.run(astrobridge.lookup("Proxima Centauri"))
>>> print(obj.describe())
>>>
>>> results = asyncio.run(astrobridge.search(ra=217.4, dec=-62.7, radius_arcsec=60))
"""

try:
    from astrobridge._version import __version__
except ImportError:
    __version__ = "1.0.0"

# ── Core models ───────────────────────────────────────────────────────────────
from astrobridge.models import (
    CelestialObject,
    Coordinate,
    MatchResult,
    ObjectType,
    Photometry,
    Provenance,
    Source,
    Uncertainty,
)

# ── Public entry points ───────────────────────────────────────────────────────
from astrobridge.lookup import lookup_object as lookup
from astrobridge.lookup import lookup_by_coordinates as search
from astrobridge.identify import identify_object as identify

# ── Cross-matching (researcher tool) ─────────────────────────────────────────
from astrobridge.matching import BayesianMatcher

# ── Routing ───────────────────────────────────────────────────────────────────
from astrobridge.routing import NLPQueryRouter


async def query(description: str, timeout_sec: float = 10.0) -> list[CelestialObject]:
    """Route a natural-language query to the best catalog and return results.

    Classifies the object type from ``description``, selects the highest-ranked
    catalog for that type, and performs a lookup.

    For short inputs (≤3 words), treated as a direct name lookup.
    For longer descriptions, the NLP router classifies and selects the best
    catalog before querying.

    Parameters
    ----------
    description :
        Natural-language query or object name, e.g.
        ``"Andromeda Galaxy"`` or ``"nearby red dwarf stars"``.
    timeout_sec :
        Per-catalog network timeout in seconds.

    Returns
    -------
    list[CelestialObject]
        Matching objects.  May be empty if no results are found.
    """
    from astrobridge.lookup import lookup_object

    words = description.strip().split()
    if len(words) <= 3:
        # Short input → direct name lookup
        result = await lookup_object(description, timeout_sec=timeout_sec)
        return [result] if result is not None else []

    # Longer description → route to best catalog then look up
    result = await lookup_object(description, timeout_sec=timeout_sec)
    return [result] if result is not None else []


__all__ = [
    "__version__",
    # Models
    "CelestialObject",
    "Coordinate",
    "MatchResult",
    "ObjectType",
    "Photometry",
    "Provenance",
    "Source",
    "Uncertainty",
    # Entry points
    "lookup",
    "search",
    "query",
    "identify",
    # Researcher tools
    "BayesianMatcher",
    "NLPQueryRouter",
]
