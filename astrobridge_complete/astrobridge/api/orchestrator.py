"""AstroBridgeOrchestrator: fan-out queries, cross-match, return unified results.

Responsibilities
----------------
1. Accept a QueryRequest.
2. Optionally route it through NLPQueryRouter to select which catalogs to hit.
3. Fan out async queries to all selected connectors.
4. Cross-match the returned sources using BayesianMatcher (if configured).
5. Apply matcher controls from the request (proper motion, weights, profiles).
6. Return a QueryResponse with sources + matches + timing metadata.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from astrobridge.api.schemas import (
    CoordinateRequest,
    MatchResponse,
    QueryRequest,
    QueryResponse,
    SourceResponse,
)
from astrobridge.connectors import CatalogConnector
from astrobridge.matching.confidence import WEIGHTING_PROFILES
from astrobridge.models import Source

logger = logging.getLogger(__name__)


class AstroBridgeOrchestrator:
    """Central coordinator for multi-catalog astronomical queries.

    Parameters
    ----------
    router :
        Optional NLPQueryRouter for catalog selection and radius estimation.
    matcher :
        Optional BayesianMatcher for cross-catalog matching.
    connectors :
        Initial mapping of catalog_name → connector.
    """

    def __init__(
        self,
        router=None,
        matcher=None,
        connectors: Optional[dict[str, CatalogConnector]] = None,
    ) -> None:
        self.router = router
        self.matcher = matcher
        self.connectors: dict[str, CatalogConnector] = dict(connectors or {})

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_connector(self, name: str, connector: CatalogConnector) -> None:
        self.connectors[name] = connector

    def set_router(self, router) -> None:  # type: ignore[no-untyped-def]
        self.router = router

    def set_matcher(self, matcher) -> None:  # type: ignore[no-untyped-def]
        self.matcher = matcher

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """Execute a query and return the unified response."""
        start_ms = time.perf_counter() * 1000.0
        query_id = str(uuid.uuid4())
        errors: list[str] = []
        routing_reasoning: Optional[str] = None
        search_radius_arcsec = 60.0

        # 1. Decide which connectors to use
        active_names = list(request.catalogs or self.connectors.keys())
        if request.auto_route and self.router is not None and request.query_type in (
            "name", "natural_language"
        ):
            query_text = request.name or request.description or ""
            try:
                decision = self.router.parse_query(query_text)
                routing_reasoning = decision.reasoning
                search_radius_arcsec = decision.search_radius_arcsec
                # Prefer catalogs the router recommends; fall back to all registered
                router_names = {
                    ct.value.lower().replace("-", "").replace(" ", "")
                    for ct, _ in decision.catalog_priority[:5]
                }
                filtered = [
                    n for n in active_names
                    if n.lower().replace("-", "").replace(" ", "") in router_names
                ]
                if filtered:
                    active_names = filtered
            except Exception as exc:
                logger.warning("Router failed: %s", exc)
                errors.append(f"Routing error: {exc}")

        active_connectors = {
            n: c for n, c in self.connectors.items() if n in active_names
        }

        # 2. Apply matcher controls from request
        if self.matcher is not None:
            self._apply_matcher_controls(request)

        # 3. Fan out
        raw_sources: dict[str, list[Source]] = {}
        if request.query_type == "name":
            raw_sources = await self._fan_out_name(
                request.name or "", active_connectors
            )
        elif request.query_type == "coordinates":
            coord = request.coordinate_request()
            if coord is not None:
                raw_sources = await self._fan_out_cone(coord, search_radius_arcsec, active_connectors)
        elif request.query_type == "natural_language":
            raw_sources = await self._fan_out_name(
                request.description or "", active_connectors
            )

        # 4. Flatten and convert to responses
        all_sources: list[Source] = []
        for _catalog_name, sources in raw_sources.items():
            all_sources.extend(sources)

        source_responses = [
            self._source_to_response(src, src.provenance.catalog_name.lower())
            for src in all_sources
        ]

        # 5. Cross-match
        match_responses = self._cross_match_sources(source_responses)

        # 6. Build response
        elapsed_ms = time.perf_counter() * 1000.0 - start_ms
        status = "success" if not errors else "partial"

        return QueryResponse(
            query_id=query_id,
            timestamp=datetime.utcnow(),
            status=status,
            query_type=request.query_type,
            catalogs_queried=list(active_connectors.keys()),
            sources=source_responses,
            matches=match_responses,
            execution_time_ms=round(elapsed_ms, 3),
            errors=errors,
            routing_reasoning=routing_reasoning,
        )

    # ------------------------------------------------------------------
    # Fan-out helpers
    # ------------------------------------------------------------------

    async def _fan_out_name(
        self,
        name: str,
        connectors: dict[str, CatalogConnector],
    ) -> dict[str, list[Source]]:
        if not name.strip() or not connectors:
            return {}

        tasks = {
            n: asyncio.create_task(c.query_object(name))
            for n, c in connectors.items()
        }
        results: dict[str, list[Source]] = {}
        for n, task in tasks.items():
            try:
                results[n] = await task
            except Exception as exc:
                logger.error("Connector %s query_object failed: %s", n, exc)
                results[n] = []
        return results

    async def _fan_out_cone(
        self,
        coord: CoordinateRequest,
        radius_arcsec: float,
        connectors: dict[str, CatalogConnector],
    ) -> dict[str, list[Source]]:
        from astrobridge.models import Coordinate
        coordinate = Coordinate(ra=coord.ra, dec=coord.dec)
        effective_radius = coord.radius_arcsec if coord.radius_arcsec != 60.0 else radius_arcsec

        tasks = {
            n: asyncio.create_task(c.cone_search(coordinate, effective_radius))
            for n, c in connectors.items()
        }
        results: dict[str, list[Source]] = {}
        for n, task in tasks.items():
            try:
                results[n] = await task
            except Exception as exc:
                logger.error("Connector %s cone_search failed: %s", n, exc)
                results[n] = []
        return results

    # ------------------------------------------------------------------
    # Matcher controls
    # ------------------------------------------------------------------

    def _apply_matcher_controls(self, request: QueryRequest) -> None:
        """Push request-level matcher options down to matcher and confidence scorer."""
        if self.matcher is None:
            return

        if request.proper_motion_aware:
            self.matcher.proper_motion_aware = True
        if request.match_epoch is not None:
            self.matcher.match_epoch = request.match_epoch

        scorer = getattr(self.matcher, "confidence_scorer", None)
        if scorer is None:
            return

        # Named profile takes priority over individual weights
        if request.weighting_profile is not None:
            profile = request.weighting_profile
            scorer.weighting_profile = profile
            if profile in WEIGHTING_PROFILES:
                astro_w, photo_w = WEIGHTING_PROFILES[profile]
                scorer.astrometric_weight = astro_w
                scorer.photometric_weight = photo_w
        else:
            if request.astrometric_weight is not None:
                scorer.astrometric_weight = request.astrometric_weight
            if request.photometric_weight is not None:
                scorer.photometric_weight = request.photometric_weight

    # ------------------------------------------------------------------
    # Cross-matching
    # ------------------------------------------------------------------

    def _cross_match_sources(
        self, sources: list[SourceResponse]
    ) -> list[MatchResponse]:
        """Cross-match a flat list of SourceResponses using the configured matcher."""
        if self.matcher is None or len(sources) < 2:
            return []

        # Reconstruct minimal Source objects from responses for the matcher
        from astrobridge.models import Coordinate, Photometry, Provenance, Source, Uncertainty

        def _to_source(sr: SourceResponse) -> Source:
            phot = (
                [Photometry(magnitude=sr.magnitude, band="V")]
                if sr.magnitude is not None
                else []
            )
            return Source(
                id=sr.id,
                name=sr.name,
                coordinate=Coordinate(ra=sr.ra, dec=sr.dec),
                uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
                photometry=phot,
                provenance=Provenance(
                    catalog_name=sr.catalog,
                    catalog_version="response",
                    query_timestamp=datetime.utcnow(),
                    source_id=sr.id,
                ),
            )

        # Partition by catalog to avoid matching a source against itself
        by_catalog: dict[str, list[SourceResponse]] = {}
        for sr in sources:
            by_catalog.setdefault(sr.catalog, []).append(sr)

        catalog_names = list(by_catalog.keys())
        match_responses: list[MatchResponse] = []

        # Match each catalog pair
        for i in range(len(catalog_names)):
            for j in range(i + 1, len(catalog_names)):
                refs = [_to_source(s) for s in by_catalog[catalog_names[i]]]
                cands = [_to_source(s) for s in by_catalog[catalog_names[j]]]
                try:
                    raw_matches = self.matcher.match(refs, cands)
                except Exception as exc:
                    logger.error("Matcher failed: %s", exc)
                    continue

                sr_by_id = {s.id: s for s in sources}
                for mr in raw_matches:
                    s1 = sr_by_id.get(mr.source1_id)
                    s2 = sr_by_id.get(mr.source2_id)
                    if s1 and s2:
                        match_responses.append(
                            MatchResponse(
                                source1=s1,
                                source2=s2,
                                match_probability=mr.match_probability,
                                separation_arcsec=mr.separation_arcsec,
                                confidence=mr.confidence,
                            )
                        )

        return match_responses

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _source_to_response(source: Source, catalog: str) -> SourceResponse:
        magnitude: Optional[float] = None
        if source.photometry:
            v_band = next(
                (p for p in source.photometry if p.band == "V"), None
            )
            magnitude = v_band.magnitude if v_band else source.photometry[0].magnitude

        return SourceResponse(
            id=source.id,
            name=source.name,
            ra=source.coordinate.ra,
            dec=source.coordinate.dec,
            catalog=catalog,
            magnitude=magnitude,
        )
