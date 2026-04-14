"""Live catalog lookup — fan-out to real catalogs, no local database required.

Two-step lookup strategy
------------------------
1. **Name resolution** — SIMBAD and NED support object names; fan out to both
   concurrently.  If either returns a match the position is known.
2. **Positional enrichment** — Gaia DR3 and 2MASS do not have a human-readable
   name index but have excellent cone-search coverage.  Once step 1 gives us
   coordinates, we issue concurrent cone searches to all position-based
   catalogs and merge everything into one ``UnifiedObject``.

Live queries require ``pyvo`` (``pip install -e .[live]``).  If not installed,
the pipeline falls back to local deterministic connectors automatically.

Supported catalogs
------------------
Name-lookup:  SIMBAD (CDS TAP), NED (IPAC TAP)
Position-lookup: Gaia DR3 (ESA TAP), 2MASS via IRSA (IPAC TAP)
Local fallback: SimbadConnector, NEDConnector (tiny built-in dataset)

Environment variables
---------------------
ASTROBRIDGE_TIMEOUT  : float  Per-catalog query timeout in seconds (default 10).
ASTROBRIDGE_ENRICH_RADIUS : float  Cone radius in arcsec for step-2 enrichment (default 5).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from astrobridge.models import Coordinate, Source, UnifiedObject

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = float(os.getenv("ASTROBRIDGE_TIMEOUT", "10"))
_ENRICH_RADIUS = float(os.getenv("ASTROBRIDGE_ENRICH_RADIUS", "5"))
_CLUSTER_RADIUS_ARCSEC = 2.0


# ---------------------------------------------------------------------------
# Adapter factories
# ---------------------------------------------------------------------------

def _name_resolvers(live: bool) -> list:
    """SIMBAD + NED — both support object-name lookup."""
    if live:
        try:
            import pyvo  # noqa: F401  # type: ignore[import-untyped]

            from astrobridge.connectors import NedTapAdapter, SimbadTapAdapter
            return [SimbadTapAdapter(), NedTapAdapter()]
        except (ImportError, RuntimeError):
            pass
    from astrobridge.connectors import NEDConnector, SimbadConnector
    return [SimbadConnector(), NEDConnector()]


def _position_enrichers(live: bool) -> list:
    """Gaia DR3 + 2MASS — cone-search only, no name index."""
    if not live:
        return []
    try:
        import pyvo  # noqa: F401  # type: ignore[import-untyped]

        from astrobridge.connectors import GaiaDR3TapAdapter, TwoMassTapAdapter
        return [GaiaDR3TapAdapter(), TwoMassTapAdapter()]
    except (ImportError, RuntimeError):
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _query_one_by_name(connector, name: str, timeout: float) -> list[Source]:
    try:
        return await asyncio.wait_for(connector.query_object(name), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("%s name query timed out for '%s'", type(connector).__name__, name)
        return []
    except Exception as exc:
        logger.warning("%s name query failed for '%s': %s", type(connector).__name__, name, exc)
        return []


async def _cone_one(connector, coord: Coordinate, radius: float, timeout: float) -> list[Source]:
    try:
        return await asyncio.wait_for(connector.cone_search(coord, radius), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("%s cone search timed out", type(connector).__name__)
        return []
    except Exception as exc:
        logger.warning("%s cone search failed: %s", type(connector).__name__, exc)
        return []


def _cluster_sources(sources: list[Source], cluster_radius: float = _CLUSTER_RADIUS_ARCSEC) -> list[list[Source]]:
    """Greedy O(n²) spatial clustering into groups within cluster_radius arcsec."""
    from astrobridge.geometry import angular_distance_arcsec

    clusters: list[list[Source]] = []
    for src in sources:
        placed = False
        for cluster in clusters:
            ref = cluster[0]
            sep = angular_distance_arcsec(
                ref.coordinate.ra, ref.coordinate.dec,
                src.coordinate.ra, src.coordinate.dec,
            )
            if sep <= cluster_radius:
                cluster.append(src)
                placed = True
                break
        if not placed:
            clusters.append([src])
    return clusters


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def lookup_object(
    name: str,
    timeout_sec: float = _DEFAULT_TIMEOUT,
    enrich_radius_arcsec: float = _ENRICH_RADIUS,
    live: bool = True,
) -> Optional[UnifiedObject]:
    """Query real astronomical catalogs and return a merged UnifiedObject.

    Uses a two-step strategy:
    1. Fan-out name queries to SIMBAD + NED concurrently.
    2. If a position is found, enrich with Gaia DR3 + 2MASS cone searches.

    Parameters
    ----------
    name :
        Object name or designation (e.g. ``"M31"``, ``"Proxima Centauri"``).
    timeout_sec :
        Per-catalog network timeout in seconds.
    enrich_radius_arcsec :
        Cone radius in arcsec for step-2 positional enrichment (default 5″).
    live :
        If True (default), attempt live TAP queries.
        If False, use only local connectors (tests / offline mode).

    Returns
    -------
    UnifiedObject or None
    """
    # Step 1: name resolution via SIMBAD + NED
    resolvers = _name_resolvers(live)
    name_batches: list[list[Source]] = await asyncio.gather(
        *[_query_one_by_name(c, name, timeout_sec) for c in resolvers]
    )
    name_sources: list[Source] = [s for batch in name_batches for s in batch]

    if not name_sources:
        logger.info("No catalog results found for '%s'", name)
        return None

    # Step 2: positional enrichment with Gaia DR3 + 2MASS
    enrichers = _position_enrichers(live)
    all_sources = list(name_sources)

    if enrichers:
        # Use the first returned source as the reference position
        ref_src = name_sources[0]
        coord = Coordinate(ra=ref_src.coordinate.ra, dec=ref_src.coordinate.dec)
        enrich_batches: list[list[Source]] = await asyncio.gather(
            *[_cone_one(c, coord, enrich_radius_arcsec, timeout_sec) for c in enrichers]
        )
        for batch in enrich_batches:
            all_sources.extend(batch)

    return UnifiedObject.from_sources(all_sources)


async def lookup_by_coordinates(
    ra: float,
    dec: float,
    radius_arcsec: float = 60.0,
    timeout_sec: float = _DEFAULT_TIMEOUT,
    live: bool = True,
) -> list[UnifiedObject]:
    """Cone-search all catalogs around (RA, Dec) and return merged objects.

    Queries SIMBAD, NED, Gaia DR3, and 2MASS concurrently.

    Parameters
    ----------
    ra, dec :
        Sky position in degrees (ICRS).
    radius_arcsec :
        Search radius in arcseconds.
    timeout_sec :
        Per-catalog timeout.
    live :
        Attempt live TAP queries when True.

    Returns
    -------
    list[UnifiedObject]
        One UnifiedObject per distinct sky position found.
    """
    coord = Coordinate(ra=ra, dec=dec)

    # All connectors support cone search
    all_connectors = _name_resolvers(live) + _position_enrichers(live)

    per_catalog = await asyncio.gather(
        *[_cone_one(c, coord, radius_arcsec, timeout_sec) for c in all_connectors]
    )
    all_sources: list[Source] = [s for batch in per_catalog for s in batch]

    if not all_sources:
        return []

    clusters = _cluster_sources(all_sources)
    return [UnifiedObject.from_sources(c) for c in clusters]
