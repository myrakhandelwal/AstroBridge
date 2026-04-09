"""API orchestrator for multi-catalog queries."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Mapping
from datetime import datetime
from typing import Optional, Protocol

from astrobridge.connectors import CatalogConnector
from astrobridge.matching.confidence import ConfidenceScorer
from astrobridge.models import Coordinate, Source
from astrobridge.routing.base import QueryRouter

from .schemas import MatchResponse, QueryRequest, QueryResponse, SourceResponse

logger = logging.getLogger(__name__)


class OrchestrationError(Exception):
    """Exception raised during query orchestration."""
    pass


class _MatchResultLike(Protocol):
    source1_id: str
    source2_id: str
    match_probability: float
    separation_arcsec: float
    confidence: float


class _MatcherLike(Protocol):
    proper_motion_aware: bool
    match_epoch: Optional[datetime]
    confidence_scorer: ConfidenceScorer

    def match(self, sources1: list[Source], sources2: list[Source]) -> list[_MatchResultLike]:
        ...


class AstroBridgeOrchestrator:
    """Orchestrates multi-catalog queries and cross-matching."""
    
    def __init__(
        self,
        router: Optional[QueryRouter] = None,
        matcher: Optional[_MatcherLike] = None,
        connectors: Optional[Mapping[str, CatalogConnector]] = None,
    ):
        """
        Initialize orchestrator.
        
        Args:
            router: QueryRouter instance for catalog selection
            matcher: Matcher instance for cross-matching
            connectors: Dict of catalog_name -> CatalogConnector
        """
        self.router = router
        self.matcher = matcher
        self.connectors: dict[str, CatalogConnector] = dict(connectors or {})
        logger.info(f"Initialized AstroBridgeOrchestrator with {len(self.connectors)} connectors")
    
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a multi-catalog query with automatic routing and matching.
        
        Args:
            request: QueryRequest with query parameters
            
        Returns:
            QueryResponse with results
        """
        query_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"Query {query_id}: Starting {request.query_type} query")
        
        try:
            self._apply_matcher_controls(request)

            # Determine catalogs to query
            if request.auto_route and self.router:
                routing_decision = self.router.parse_query(
                    request.description or request.name or ""
                )
                catalogs_to_query = [str(catalog) for catalog in routing_decision.get_top_catalogs(n=3)]
                routing_reasoning = routing_decision.reasoning
                logger.debug(f"Query {query_id}: Routed to {catalogs_to_query}")
            else:
                catalogs_to_query = request.catalogs or list(self.connectors.keys())
                routing_reasoning = None
                logger.debug(f"Query {query_id}: Using explicit catalogs {catalogs_to_query}")
            
            # Query catalogs
            sources_by_catalog: dict[str, list[Source]] = {}
            errors: list[str] = []
            
            query_tasks: list[Awaitable[list[Source]]] = []
            task_catalogs: list[str] = []
            for catalog in catalogs_to_query:
                if catalog in self.connectors:
                    task = self._query_catalog(query_id, catalog, request)
                    query_tasks.append(task)
                    task_catalogs.append(catalog)
                else:
                    error_msg = f"Catalog {catalog} not available"
                    errors.append(error_msg)
                    logger.warning(f"Query {query_id}: {error_msg}")
            
            # Execute all queries concurrently
            results = await asyncio.gather(*query_tasks, return_exceptions=True)
            
            for catalog, result in zip(task_catalogs, results):
                if isinstance(result, Exception):
                    errors.append(f"{catalog}: {str(result)}")
                    logger.error(f"Query {query_id}: {catalog} query failed: {result}")
                else:
                    sources_by_catalog[catalog] = result
            
            # Flatten all sources and convert to API response models.
            all_sources: list[Source] = []
            source_responses: list[SourceResponse] = []
            for catalog, sources in sources_by_catalog.items():
                all_sources.extend(sources)
                source_responses.extend(
                    self._source_to_response(source, catalog)
                    for source in sources
                )
            
            # Cross-match sources
            matches: list[MatchResponse] = []
            if self.matcher and len(all_sources) > 1:
                try:
                    matches = self._cross_match_sources(sources_by_catalog)
                    logger.debug(f"Query {query_id}: Found {len(matches)} matches")
                except Exception as e:
                    logger.error(f"Query {query_id}: Cross-matching failed: {e}")
                    errors.append(f"Cross-matching failed: {str(e)}")
            
            # Build response
            execution_time_ms = (time.time() - start_time) * 1000
            status = "success" if not errors else ("partial" if sources_by_catalog else "error")
            
            response = QueryResponse(
                query_id=query_id,
                timestamp=datetime.utcnow(),
                status=status,
                query_type=request.query_type,
                catalogs_queried=list(sources_by_catalog.keys()),
                sources=source_responses,
                matches=matches,
                routing_reasoning=routing_reasoning,
                execution_time_ms=execution_time_ms,
                errors=errors
            )
            
            logger.info(f"Query {query_id}: Completed in {execution_time_ms:.1f}ms, "
                       f"found {len(all_sources)} sources, {len(matches)} matches")
            
            return response
            
        except Exception as e:
            logger.error(f"Query {query_id}: Orchestration failed: {e}")
            execution_time_ms = (time.time() - start_time) * 1000
            
            return QueryResponse(
                query_id=query_id,
                timestamp=datetime.utcnow(),
                status="error",
                query_type=request.query_type,
                catalogs_queried=[],
                sources=[],
                matches=[],
                execution_time_ms=execution_time_ms,
                errors=[str(e)]
            )

    def _apply_matcher_controls(self, request: QueryRequest) -> None:
        """Apply optional matcher controls from API request."""
        if self.matcher is None:
            return

        if hasattr(self.matcher, "proper_motion_aware"):
            self.matcher.proper_motion_aware = bool(request.proper_motion_aware)

        if hasattr(self.matcher, "match_epoch"):
            self.matcher.match_epoch = request.match_epoch

        if (
            request.astrometric_weight is None
            and request.photometric_weight is None
            and request.weighting_profile is None
        ):
            return

        existing = getattr(self.matcher, "confidence_scorer", None)
        if existing is None:
            existing = ConfidenceScorer()

        if request.weighting_profile is not None:
            profiled = ConfidenceScorer.from_profile(
                request.weighting_profile,
                uncertainty_scaling=existing.uncertainty_scaling,
                max_separation_arcsec=existing.max_separation_arcsec,
            )
            astrometric_weight = profiled.astrometric_weight
            photometric_weight = profiled.photometric_weight
            weighting_profile = request.weighting_profile
        else:
            astrometric_weight = existing.astrometric_weight
            photometric_weight = existing.photometric_weight
            weighting_profile = getattr(existing, "weighting_profile", "balanced")

        # Explicit per-request weights override profile values when provided.
        if request.astrometric_weight is not None:
            astrometric_weight = request.astrometric_weight
            weighting_profile = "custom"
        if request.photometric_weight is not None:
            photometric_weight = request.photometric_weight
            weighting_profile = "custom"

        if hasattr(self.matcher, "confidence_scorer"):
            self.matcher.confidence_scorer = ConfidenceScorer(
                astrometric_weight=astrometric_weight,
                photometric_weight=photometric_weight,
                uncertainty_scaling=existing.uncertainty_scaling,
                max_separation_arcsec=existing.max_separation_arcsec,
                weighting_profile=weighting_profile,
            )
    
    async def _query_catalog(
        self,
        query_id: str,
        catalog: str,
        request: QueryRequest
    ) -> list[Source]:
        """
        Query a single catalog.
        
        Args:
            query_id: Query identifier
            catalog: Catalog name
            request: Query request
            
        Returns:
            List of sources found
        """
        if catalog not in self.connectors:
            raise OrchestrationError(f"Connector not configured for {catalog}")
        
        connector = self.connectors[catalog]
        sources = []
        
        try:
            lookup_value = request.name or request.description or ""

            if request.query_type in {"name", "natural_language"} and lookup_value:
                results = await connector.query_object(lookup_value)
                sources.extend(results)
            
            elif request.query_type == "coordinates" and request.coordinates:
                center = Coordinate(
                    ra=request.coordinates.ra,
                    dec=request.coordinates.dec,
                )
                results = await connector.cone_search(
                    center,
                    request.coordinates.radius_arcsec,
                )
                sources.extend(results)
            
            logger.debug(f"Query {query_id}: {catalog} returned {len(sources)} sources")
            
        except Exception as e:
            logger.error(f"Query {query_id}: {catalog} query error: {e}")
            raise
        
        return sources
    
    def _source_to_response(self, source: Source, catalog: str) -> SourceResponse:
        """Convert a Source model to SourceResponse.
        
        Safely extracts the first magnitude from photometry list, defaulting to None
        if the list is empty or missing.
        """
        # Use next() with default instead of [0] to safely handle empty sequences
        first_magnitude = next(
            (p.magnitude for p in source.photometry),
            None  # Default value if generator is exhausted
        ) if source.photometry else None
        
        return SourceResponse(
            id=source.id,
            name=source.name,
            ra=source.coordinate.ra,
            dec=source.coordinate.dec,
            catalog=catalog,
            object_type=None,
            magnitude=first_magnitude,
        )
    
    def _cross_match_sources(self, sources_by_catalog: dict[str, list[Source]]) -> list[MatchResponse]:
        """
        Cross-match sources from different catalogs.
        
        Args:
            sources_by_catalog: Sources grouped by catalog name
            
        Returns:
            List of matched sources
        """
        if not self.matcher or len(sources_by_catalog) < 2:
            return []

        # Build lookup tables once so match result conversion is deterministic.
        response_lookup = {
            catalog: {
                source.id: self._source_to_response(source, catalog)
                for source in sources
            }
            for catalog, sources in sources_by_catalog.items()
        }

        matches = []
        catalogs = list(sources_by_catalog.keys())

        for i, cat1 in enumerate(catalogs):
            for cat2 in catalogs[i + 1:]:
                raw_matches = self.matcher.match(
                    sources_by_catalog[cat1],
                    sources_by_catalog[cat2],
                )
                for raw_match in raw_matches:
                    source1 = response_lookup[cat1].get(raw_match.source1_id)
                    source2 = response_lookup[cat2].get(raw_match.source2_id)
                    if source1 is None or source2 is None:
                        continue
                    matches.append(
                        MatchResponse(
                            source1=source1,
                            source2=source2,
                            match_probability=raw_match.match_probability,
                            separation_arcsec=raw_match.separation_arcsec,
                            confidence=raw_match.confidence,
                        )
                    )

        return matches
    
    def add_connector(self, catalog: str, connector: CatalogConnector) -> None:
        """
        Register a catalog connector.
        
        Args:
            catalog: Catalog name
            connector: CatalogConnector instance
        """
        self.connectors[catalog] = connector
        logger.info(f"Registered connector for {catalog}")
    
    def set_router(self, router: QueryRouter) -> None:
        """Set the query router for intelligent catalog selection."""
        self.router = router
        logger.info("Set query router for intelligent routing")
    
    def set_matcher(self, matcher: _MatcherLike) -> None:
        """Set the matcher for cross-matching."""
        self.matcher = matcher
        logger.info("Set matcher for cross-matching")
