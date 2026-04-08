"""API orchestrator for multi-catalog queries."""
import logging
import asyncio
import time
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from .schemas import QueryRequest, QueryResponse, SourceResponse, MatchResponse
from astrobridge.matching.confidence import ConfidenceScorer

logger = logging.getLogger(__name__)


class OrchestrationError(Exception):
    """Exception raised during query orchestration."""
    pass


class AstroBridgeOrchestrator:
    """Orchestrates multi-catalog queries and cross-matching."""
    
    def __init__(self, router=None, matcher=None, connectors=None):
        """
        Initialize orchestrator.
        
        Args:
            router: QueryRouter instance for catalog selection
            matcher: Matcher instance for cross-matching
            connectors: Dict of catalog_name -> CatalogConnector
        """
        self.router = router
        self.matcher = matcher
        self.connectors = connectors or {}
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
                catalogs_to_query = routing_decision.get_top_catalogs(n=3)
                routing_reasoning = routing_decision.reasoning
                logger.debug(f"Query {query_id}: Routed to {catalogs_to_query}")
            else:
                catalogs_to_query = request.catalogs or list(self.connectors.keys())
                routing_reasoning = None
                logger.debug(f"Query {query_id}: Using explicit catalogs {catalogs_to_query}")
            
            # Query catalogs
            sources_by_catalog = {}
            errors = []
            
            query_tasks = []
            for catalog in catalogs_to_query:
                if catalog in self.connectors:
                    task = self._query_catalog(query_id, catalog, request)
                    query_tasks.append(task)
                else:
                    error_msg = f"Catalog {catalog} not available"
                    errors.append(error_msg)
                    logger.warning(f"Query {query_id}: {error_msg}")
            
            # Execute all queries concurrently
            results = await asyncio.gather(*query_tasks, return_exceptions=True)
            
            for catalog, result in zip(catalogs_to_query, results):
                if isinstance(result, Exception):
                    errors.append(f"{catalog}: {str(result)}")
                    logger.error(f"Query {query_id}: {catalog} query failed: {result}")
                else:
                    sources_by_catalog[catalog] = result
            
            # Flatten all sources
            all_sources = []
            for catalog, sources in sources_by_catalog.items():
                all_sources.extend(sources)
            
            # Cross-match sources
            matches = []
            if self.matcher and len(all_sources) > 1:
                try:
                    matches = self._cross_match_sources(all_sources)
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
                sources=all_sources,
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
    ) -> List[SourceResponse]:
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
                result = connector.query(lookup_value)
                if result:
                    sources.append(self._source_to_response(result, catalog))
            
            elif request.query_type == "coordinates" and request.coordinates:
                # Note: This requires cone_search method not yet implemented
                logger.info(f"Query {query_id}: Coordinate search for {catalog} skipped (not implemented)")
            
            logger.debug(f"Query {query_id}: {catalog} returned {len(sources)} sources")
            
        except Exception as e:
            logger.error(f"Query {query_id}: {catalog} query error: {e}")
            raise
        
        return sources
    
    def _source_to_response(self, source: Any, catalog: str) -> SourceResponse:
        """Convert a Source model to SourceResponse."""
        from astrobridge.models import Source
        
        if isinstance(source, Source):
            return SourceResponse(
                id=source.id,
                name=source.name,
                ra=source.coordinate.ra,
                dec=source.coordinate.dec,
                catalog=catalog,
                object_type=None,  # Would come from source metadata
                magnitude=source.photometry[0].magnitude if source.photometry else None
            )
        
        raise ValueError(f"Unsupported source type: {type(source)}")
    
    def _cross_match_sources(self, sources: List[SourceResponse]) -> List[MatchResponse]:
        """
        Cross-match sources from different catalogs.
        
        Args:
            sources: List of sources from different catalogs
            
        Returns:
            List of matched sources
        """
        if not self.matcher or len(sources) < 2:
            return []
        
        # Group by catalog
        by_catalog = {}
        for source in sources:
            if source.catalog not in by_catalog:
                by_catalog[source.catalog] = []
            by_catalog[source.catalog].append(source)
        
        # Match between catalogs (simple approach: pairwise)
        matches = []
        catalogs = list(by_catalog.keys())
        
        for i, cat1 in enumerate(catalogs):
            for cat2 in catalogs[i+1:]:
                sources1 = by_catalog[cat1]
                sources2 = by_catalog[cat2]
                
                # In production, would use actual matching algorithm
                # For now, return empty matches
                pass
        
        return matches
    
    def add_connector(self, catalog: str, connector: Any) -> None:
        """
        Register a catalog connector.
        
        Args:
            catalog: Catalog name
            connector: CatalogConnector instance
        """
        self.connectors[catalog] = connector
        logger.info(f"Registered connector for {catalog}")
    
    def set_router(self, router: Any) -> None:
        """Set the query router for intelligent catalog selection."""
        self.router = router
        logger.info("Set query router for intelligent routing")
    
    def set_matcher(self, matcher: Any) -> None:
        """Set the matcher for cross-matching."""
        self.matcher = matcher
        logger.info("Set matcher for cross-matching")
