"""Multi-catalog query engine with automatic cross-matching."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .connectors import CatalogConnector
from .geometry import angular_distance_arcsec
from .models import Coordinate, Source, UnifiedObject

logger = logging.getLogger(__name__)


class QueryEngine:
    """Stateful engine for multi-catalog fan-out queries and source merging.

    Provides a simpler alternative to the full API orchestrator for
    programmatic use.  Register connectors, then call ``query_by_name``
    or ``query_by_coordinates`` to get a list of merged
    :class:`UnifiedObject` instances.
    """

    def __init__(
        self,
        connectors: Optional[dict[str, CatalogConnector]] = None,
        match_radius_arcsec: float = 2.0,
    ) -> None:
        self.connectors: dict[str, CatalogConnector] = dict(connectors or {})
        self.match_radius_arcsec = match_radius_arcsec

    def register(self, catalog_name: str, connector: CatalogConnector) -> None:
        """Add or replace a catalog connector."""
        self.connectors[catalog_name] = connector

    async def query_by_name(self, name: str) -> list[UnifiedObject]:
        """Fan-out name lookup to all registered connectors and merge."""
        results: dict[str, list[Source]] = {}
        tasks = {
            catalog: asyncio.create_task(connector.query_object(name))
            for catalog, connector in self.connectors.items()
        }

        for catalog, task in tasks.items():
            try:
                sources = await task
                if sources:
                    results[catalog] = sources
            except Exception as exc:
                logger.warning("QueryEngine: %s query failed: %s", catalog, exc)

        all_sources = [s for catalog_sources in results.values() for s in catalog_sources]
        return self._merge(all_sources)

    async def query_by_coordinates(
        self,
        ra: float,
        dec: float,
        radius_arcsec: float = 60.0,
    ) -> list[UnifiedObject]:
        """Fan-out cone search to all registered connectors and merge."""
        coord = Coordinate(ra=ra, dec=dec)
        results: dict[str, list[Source]] = {}
        tasks = {
            catalog: asyncio.create_task(
                connector.cone_search(coord, radius_arcsec)
            )
            for catalog, connector in self.connectors.items()
        }

        for catalog, task in tasks.items():
            try:
                sources = await task
                if sources:
                    results[catalog] = sources
            except Exception as exc:
                logger.warning("QueryEngine: %s cone search failed: %s", catalog, exc)

        all_sources = [s for catalog_sources in results.values() for s in catalog_sources]
        return self._merge(all_sources)

    def _merge(self, sources: list[Source]) -> list[UnifiedObject]:
        """Greedy spatial clustering followed by UnifiedObject construction."""
        if not sources:
            return []

        clusters: list[list[Source]] = []
        for source in sources:
            merged = False
            for cluster in clusters:
                rep = cluster[0]
                sep = angular_distance_arcsec(
                    rep.coordinate.ra,
                    rep.coordinate.dec,
                    source.coordinate.ra,
                    source.coordinate.dec,
                )
                if sep <= self.match_radius_arcsec:
                    cluster.append(source)
                    merged = True
                    break
            if not merged:
                clusters.append([source])

        return [UnifiedObject.from_sources(cluster) for cluster in clusters]
