"""Query engine: coordinates multi-catalog queries and merges results.

This is the primary entry point for the pipeline.  It:
1. Accepts a name or (RA, Dec) query.
2. Fans out to all registered connectors concurrently.
3. Clusters results by angular proximity (Haversine, 2-arcsec default).
4. Returns a list of ``UnifiedObject`` instances, each merging sources from
   all catalogs that returned the same sky position.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from typing import Optional

from astrobridge.catalog_connectors import CatalogConnector
from astrobridge.geometry import angular_distance_arcsec
from astrobridge.models import Source, UnifiedObject

logger = logging.getLogger(__name__)

DEFAULT_MATCH_RADIUS_ARCSEC = 2.0


class QueryEngine:
    """Fan-out to multiple catalog connectors and merge results.

    Parameters
    ----------
    connectors :
        Mapping of catalog name → connector instance.
    match_radius_arcsec :
        Maximum angular separation (Haversine) to cluster sources from
        different catalogs as the same object.
    conn :
        Optional open SQLite connection.  Used to cache AI descriptions and
        persist objects; pass None to skip persistence.
    """

    def __init__(
        self,
        connectors: Optional[dict[str, CatalogConnector]] = None,
        match_radius_arcsec: float = DEFAULT_MATCH_RADIUS_ARCSEC,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        self._connectors: dict[str, CatalogConnector] = connectors or {}
        self.match_radius_arcsec = match_radius_arcsec
        self._conn = conn

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, catalog_name: str, connector: CatalogConnector) -> None:
        """Add or replace a connector."""
        self._connectors[catalog_name] = connector

    # ------------------------------------------------------------------
    # Public query interface
    # ------------------------------------------------------------------

    async def query_by_name(self, name: str) -> list[UnifiedObject]:
        """Query all connectors by object name and return merged objects."""
        if not self._connectors:
            logger.warning("No connectors registered in QueryEngine.")
            return []

        tasks = {
            catalog: asyncio.create_task(connector.query_object(name))
            for catalog, connector in self._connectors.items()
        }
        results: dict[str, list[Source]] = {}
        for catalog, task in tasks.items():
            try:
                results[catalog] = await task
            except Exception as exc:
                logger.error("Connector %s failed for name=%s: %s", catalog, name, exc)
                results[catalog] = []

        return self._merge(results)

    async def query_by_coordinates(
        self,
        ra: float,
        dec: float,
        radius_arcsec: float = 60.0,
    ) -> list[UnifiedObject]:
        """Cone-search all connectors and return merged objects."""
        if not self._connectors:
            logger.warning("No connectors registered in QueryEngine.")
            return []

        tasks = {
            catalog: asyncio.create_task(
                connector.cone_search(__import__("astrobridge.models", fromlist=["Coordinate"]).Coordinate(ra=ra, dec=dec), radius_arcsec)
            )
            for catalog, connector in self._connectors.items()
        }
        results: dict[str, list[Source]] = {}
        for catalog, task in tasks.items():
            try:
                results[catalog] = await task
            except Exception as exc:
                logger.error(
                    "Connector %s failed for cone search RA=%s Dec=%s: %s",
                    catalog,
                    ra,
                    dec,
                    exc,
                )
                results[catalog] = []

        return self._merge(results)

    # ------------------------------------------------------------------
    # Clustering / merging
    # ------------------------------------------------------------------

    def _merge(self, results: dict[str, list[Source]]) -> list[UnifiedObject]:
        """Cluster all returned sources into unified objects.

        Algorithm (greedy, O(n²)):
        1. Flatten all sources into a single list, tagged by catalog.
        2. Iterate: assign each unvisited source to the first existing cluster
           whose centroid is within ``match_radius_arcsec``, or start a new one.
        3. Build one UnifiedObject per cluster.
        """
        flat: list[Source] = []
        for sources in results.values():
            flat.extend(sources)

        if not flat:
            return []

        # Clusters are lists of Source objects
        clusters: list[list[Source]] = []

        for src in flat:
            placed = False
            for cluster in clusters:
                ref = cluster[0]
                sep = angular_distance_arcsec(
                    ref.coordinate.ra,
                    ref.coordinate.dec,
                    src.coordinate.ra,
                    src.coordinate.dec,
                )
                if sep <= self.match_radius_arcsec:
                    cluster.append(src)
                    placed = True
                    break
            if not placed:
                clusters.append([src])

        unified: list[UnifiedObject] = []
        for cluster in clusters:
            try:
                obj = UnifiedObject.from_sources(cluster)
                unified.append(obj)
            except Exception as exc:
                logger.error("Failed to build UnifiedObject from cluster: %s", exc)

        logger.info(
            "Merged %d raw sources from %d catalogs into %d unified objects",
            len(flat),
            len(results),
            len(unified),
        )
        return unified
