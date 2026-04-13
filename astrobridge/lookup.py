"""Live catalog lookup — fan-out to real catalogs, no local database required.

Priority order for each query:
1. SIMBAD TAP (live, requires ``pyvo`` via ``pip install -e .[live]``)
2. NED TAP   (live, same requirement)
3. Local deterministic connectors (always available, tiny dataset)

Results from all reachable catalogs are merged into a single ``UnifiedObject``.
Returns ``None`` if the object cannot be found anywhere.

Environment variables
---------------------
ASTROBRIDGE_TIMEOUT  : float  Per-catalog query timeout in seconds (default 10).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from astrobridge.models import Source, UnifiedObject

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = float(os.getenv("ASTROBRIDGE_TIMEOUT", "10"))


def _try_tap_adapters() -> list:
    """Return live TAP adapters if pyvo is installed, else empty list."""
    try:
        import pyvo  # noqa: F401  # type: ignore[import-untyped]
        from astrobridge.connectors import NedTapAdapter, SimbadTapAdapter
        return [SimbadTapAdapter(), NedTapAdapter()]
    except (ImportError, RuntimeError):
        return []


def _local_adapters() -> list:
    """Return always-available local connectors as fallback."""
    from astrobridge.connectors import NEDConnector, SimbadConnector
    return [SimbadConnector(), NEDConnector()]


async def _query_one(connector, name: str, timeout: float) -> list[Source]:
    """Query a single connector, silencing timeouts and errors."""
    try:
        return await asyncio.wait_for(connector.query_object(name), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(
            "%s query timed out for '%s'", type(connector).__name__, name
        )
        return []
    except Exception as exc:
        logger.warning(
            "%s query failed for '%s': %s", type(connector).__name__, name, exc
        )
        return []


async def lookup_object(
    name: str,
    timeout_sec: float = _DEFAULT_TIMEOUT,
    live: bool = True,
) -> Optional[UnifiedObject]:
    """Query real astronomical catalogs and return a merged UnifiedObject.

    Parameters
    ----------
    name :
        Object name or designation (e.g. ``"M31"``, ``"Proxima Centauri"``).
    timeout_sec :
        Per-catalog network timeout in seconds.
    live :
        If True (default), attempt live TAP queries first.
        If False, use only local connectors (useful for tests / offline mode).

    Returns
    -------
    UnifiedObject or None
        Merged view across all catalogs that returned a match, or None if no
        catalog found the object.
    """
    connectors = (_try_tap_adapters() if live else []) or _local_adapters()

    # Fan out concurrently to all available connectors
    tasks = [_query_one(c, name, timeout_sec) for c in connectors]
    per_catalog: list[list[Source]] = await asyncio.gather(*tasks)

    all_sources: list[Source] = [s for batch in per_catalog for s in batch]

    if not all_sources:
        logger.info("No catalog results found for '%s'", name)
        return None

    return UnifiedObject.from_sources(all_sources)


async def lookup_by_coordinates(
    ra: float,
    dec: float,
    radius_arcsec: float = 60.0,
    timeout_sec: float = _DEFAULT_TIMEOUT,
    live: bool = True,
) -> list[UnifiedObject]:
    """Cone-search real catalogs around (RA, Dec) and return merged objects.

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
    from astrobridge.models import Coordinate

    coord = Coordinate(ra=ra, dec=dec)
    connectors = (_try_tap_adapters() if live else []) or _local_adapters()

    async def _cone_one(connector) -> list[Source]:
        try:
            return await asyncio.wait_for(
                connector.cone_search(coord, radius_arcsec), timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            logger.warning("%s cone search timed out", type(connector).__name__)
            return []
        except Exception as exc:
            logger.warning("%s cone search failed: %s", type(connector).__name__, exc)
            return []

    per_catalog = await asyncio.gather(*[_cone_one(c) for c in connectors])
    all_sources: list[Source] = [s for batch in per_catalog for s in batch]

    if not all_sources:
        return []

    # Cluster sources within 2 arcsec into unified objects
    from astrobridge.geometry import angular_distance_arcsec

    CLUSTER_RADIUS = 2.0
    clusters: list[list[Source]] = []
    for src in all_sources:
        placed = False
        for cluster in clusters:
            ref = cluster[0]
            sep = angular_distance_arcsec(
                ref.coordinate.ra, ref.coordinate.dec,
                src.coordinate.ra, src.coordinate.dec,
            )
            if sep <= CLUSTER_RADIUS:
                cluster.append(src)
                placed = True
                break
        if not placed:
            clusters.append([src])

    return [UnifiedObject.from_sources(c) for c in clusters]
