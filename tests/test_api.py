"""Tests for API orchestration."""
from datetime import datetime

import pytest

from astrobridge.api import (
    AstroBridgeOrchestrator,
    MatchResponse,
    QueryRequest,
    QueryResponse,
    SourceResponse,
)
from astrobridge.matching import BayesianMatcher
from astrobridge.routing import NLPQueryRouter


class TestQuerySchemas:
    """Test request and response schemas."""
    
    def test_source_request(self):
        """Test SourceRequest schema."""
        from astrobridge.api.schemas import SourceRequest
        req = SourceRequest(name="Proxima Centauri")
        assert req.name == "Proxima Centauri"
    
    def test_coordinate_request(self):
        """Test CoordinateRequest schema."""
        from astrobridge.api.schemas import CoordinateRequest
        req = CoordinateRequest(ra=180.0, dec=45.0, radius_arcsec=60)
        assert req.ra == 180.0
        assert req.dec == 45.0
        assert req.radius_arcsec == 60
    
    def test_coordinate_request_validation(self):
        """Test CoordinateRequest validation."""
        from astrobridge.api.schemas import CoordinateRequest
        
        # Valid RA, Dec
        req = CoordinateRequest(ra=0, dec=-90)
        assert req.ra == 0
        assert req.dec == -90
        
        # Invalid RA (>360)
        with pytest.raises(ValueError):
            CoordinateRequest(ra=361, dec=45)
        
        # Invalid Dec (>90)
        with pytest.raises(ValueError):
            CoordinateRequest(ra=180, dec=91)
    
    def test_query_request_name_type(self):
        """Test QueryRequest for name search."""
        req = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            auto_route=True
        )
        assert req.query_type == "name"
        assert req.name == "Proxima Centauri"
        assert req.auto_route is True
    
    def test_query_request_natural_language(self):
        """Test QueryRequest for natural language."""
        req = QueryRequest(
            query_type="natural_language",
            description="Find nearby red dwarf stars",
            auto_route=True
        )
        assert req.query_type == "natural_language"
        assert "red dwarf" in req.description

    def test_query_request_matcher_controls(self):
        """Test QueryRequest matcher control fields."""
        req = QueryRequest(
            query_type="name",
            name="Barnard's Star",
            proper_motion_aware=True,
            match_epoch=datetime(2020, 1, 1),
            astrometric_weight=0.8,
            photometric_weight=0.2,
        )

        assert req.proper_motion_aware is True
        assert req.match_epoch == datetime(2020, 1, 1)
        assert req.astrometric_weight == 0.8
        assert req.photometric_weight == 0.2

    def test_query_request_weight_validation(self):
        """Test QueryRequest weight validation bounds."""
        with pytest.raises(ValueError):
            QueryRequest(query_type="name", name="x", astrometric_weight=1.5)
        with pytest.raises(ValueError):
            QueryRequest(query_type="name", name="x", photometric_weight=-0.1)

    def test_query_request_weighting_profile(self):
        """Test QueryRequest weighting profile field."""
        req = QueryRequest(
            query_type="name",
            name="Test",
            weighting_profile="position_first",
        )
        assert req.weighting_profile == "position_first"
    
    def test_source_response(self):
        """Test SourceResponse schema."""
        source = SourceResponse(
            id="SIMBAD:*2MASS J12345+67890",
            name="Proxima Centauri",
            ra=217.429,
            dec=-62.680,
            catalog="simbad",
            object_type="star",
            magnitude=11.05
        )
        assert source.id == "SIMBAD:*2MASS J12345+67890"
        assert source.name == "Proxima Centauri"
        assert source.catalog == "simbad"
    
    def test_match_response(self):
        """Test MatchResponse schema."""
        source1 = SourceResponse(
            id="s1", name="Source1", ra=180.0, dec=45.0,
            catalog="simbad"
        )
        source2 = SourceResponse(
            id="s2", name="Source2", ra=180.001, dec=45.001,
            catalog="ned"
        )
        match = MatchResponse(
            source1=source1,
            source2=source2,
            match_probability=0.95,
            separation_arcsec=3.6,
            confidence=0.9
        )
        assert match.match_probability == 0.95
        assert match.separation_arcsec == 3.6
    
    def test_query_response(self):
        """Test QueryResponse schema."""
        response = QueryResponse(
            query_id="q_123",
            timestamp=datetime.utcnow(),
            status="success",
            query_type="name",
            catalogs_queried=["simbad"],
            sources=[],
            matches=[],
            execution_time_ms=100.5,
            errors=[]
        )
        assert response.query_id == "q_123"
        assert response.status == "success"
        assert response.execution_time_ms == 100.5


class TestOrchestrator:
    """Test query orchestration."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = AstroBridgeOrchestrator()
        assert orchestrator.router is None
        assert orchestrator.matcher is None
        assert len(orchestrator.connectors) == 0
    
    def test_orchestrator_with_components(self):
        """Test orchestrator with components."""
        router = NLPQueryRouter()
        matcher = BayesianMatcher()
        orchestrator = AstroBridgeOrchestrator(
            router=router,
            matcher=matcher,
            connectors={}
        )
        assert orchestrator.router is router
        assert orchestrator.matcher is matcher
    
    def test_add_connector(self):
        """Test adding a connector."""
        from astrobridge.connectors import SimbadConnector
        orchestrator = AstroBridgeOrchestrator()
        connector = SimbadConnector()
        
        orchestrator.add_connector("simbad", connector)
        assert "simbad" in orchestrator.connectors
        assert orchestrator.connectors["simbad"] is connector
    
    def test_set_router(self):
        """Test setting router."""
        orchestrator = AstroBridgeOrchestrator()
        router = NLPQueryRouter()
        
        orchestrator.set_router(router)
        assert orchestrator.router is router
    
    def test_set_matcher(self):
        """Test setting matcher."""
        orchestrator = AstroBridgeOrchestrator()
        matcher = BayesianMatcher()
        
        orchestrator.set_matcher(matcher)
        assert orchestrator.matcher is matcher


@pytest.mark.asyncio
class TestQueryExecution:
    """Test query execution."""
    
    async def test_execute_query_no_connectors(self):
        """Test query execution with no connectors."""
        orchestrator = AstroBridgeOrchestrator()
        request = QueryRequest(
            query_type="name",
            name="Test Object",
            auto_route=False
        )
        
        response = await orchestrator.execute_query(request)
        # With no connectors, status is success but no sources found
        assert response.status in ["success", "partial"]
        assert len(response.sources) == 0
        assert response.execution_time_ms > 0
    
    async def test_execute_query_with_router(self):
        """Test query execution with routing."""
        router = NLPQueryRouter()
        orchestrator = AstroBridgeOrchestrator(router=router)
        
        request = QueryRequest(
            query_type="natural_language",
            description="Find nearby red dwarf stars",
            auto_route=True
        )
        
        response = await orchestrator.execute_query(request)
        assert response.query_id is not None
        assert response.status in ["success", "partial", "error"]
        assert response.query_type == "natural_language"
        assert response.execution_time_ms > 0
        
        # Should have routing reasoning
        if response.routing_reasoning:
            assert "red dwarf" in response.routing_reasoning.lower() or \
                   "star" in response.routing_reasoning.lower()
    
    async def test_query_request_types(self):
        """Test different query request types."""
        orchestrator = AstroBridgeOrchestrator()
        
        # Name query
        req1 = QueryRequest(query_type="name", name="Proxima Centauri")
        resp1 = await orchestrator.execute_query(req1)
        assert resp1.query_type == "name"
        
        # Coordinate query
        from astrobridge.api.schemas import CoordinateRequest
        req2 = QueryRequest(
            query_type="coordinates",
            coordinates=CoordinateRequest(ra=180.0, dec=45.0)
        )
        resp2 = await orchestrator.execute_query(req2)
        assert resp2.query_type == "coordinates"
        
        # Natural language query
        req3 = QueryRequest(
            query_type="natural_language",
            description="Find stars"
        )
        resp3 = await orchestrator.execute_query(req3)
        assert resp3.query_type == "natural_language"
    
    async def test_error_handling(self):
        """Test error handling in orchestration."""
        orchestrator = AstroBridgeOrchestrator()
        
        # Minimal valid query should be handled gracefully.
        request = QueryRequest(query_type="name", name="Unknown Object")
        response = await orchestrator.execute_query(request)
        
        # Should complete without crashing
        assert response.query_id is not None
        assert response.execution_time_ms > 0

    async def test_query_request_requires_payload_per_query_type(self):
        """QueryRequest should validate required payload by query type."""
        with pytest.raises(ValueError, match="name is required"):
            QueryRequest(query_type="name")

        with pytest.raises(ValueError, match="coordinates are required"):
            QueryRequest(query_type="coordinates")

        with pytest.raises(ValueError, match="description is required"):
            QueryRequest(query_type="natural_language")

    async def test_query_request_rejects_unknown_query_type(self):
        """QueryRequest should reject unknown query types."""
        with pytest.raises(ValueError):
            QueryRequest(query_type="unknown", name="x")

    async def test_execute_query_returns_cross_catalog_matches(self):
        """Name queries across multiple connectors should emit matches."""
        from astrobridge.connectors import NEDConnector, SimbadConnector

        orchestrator = AstroBridgeOrchestrator(
            matcher=BayesianMatcher(confidence_threshold=0.01),
            connectors={
                "simbad": SimbadConnector(),
                "ned": NEDConnector(),
            },
        )

        request = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            catalogs=["simbad", "ned"],
            auto_route=False,
        )

        response = await orchestrator.execute_query(request)
        assert response.status in ["success", "partial"]
        assert len(response.sources) >= 2
        assert len(response.matches) >= 1

    async def test_execute_coordinate_query_calls_connector_cone_search(self):
        """Coordinate queries should delegate to connector cone_search."""
        from astrobridge.connectors import CatalogConnector
        from astrobridge.models import Coordinate, Photometry, Provenance, Source, Uncertainty

        class CoordinateConnector(CatalogConnector):
            def __init__(self):
                self.cone_calls = 0

            def query(self, name: str) -> None:
                return None

            async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
                self.cone_calls += 1
                return [
                    Source(
                        id="coord-1",
                        name="Coordinate Match",
                        coordinate=Coordinate(ra=coordinate.ra, dec=coordinate.dec),
                        uncertainty=Uncertainty(ra_error=0.2, dec_error=0.2),
                        photometry=[Photometry(magnitude=12.0, band="V")],
                        provenance=Provenance(
                            catalog_name="COORD",
                            catalog_version="test",
                            query_timestamp=datetime.utcnow(),
                            source_id="coord-1",
                        ),
                    )
                ]

        connector = CoordinateConnector()
        orchestrator = AstroBridgeOrchestrator(connectors={"coord": connector})
        request = QueryRequest(
            query_type="coordinates",
            coordinates={"ra": 180.0, "dec": 45.0, "radius_arcsec": 30.0},
            catalogs=["coord"],
            auto_route=False,
        )

        response = await orchestrator.execute_query(request)
        assert connector.cone_calls == 1
        assert len(response.sources) == 1

    async def test_execute_query_applies_matcher_options(self):
        """Test orchestrator applies matcher controls from request."""
        matcher = BayesianMatcher()
        orchestrator = AstroBridgeOrchestrator(matcher=matcher)

        request = QueryRequest(
            query_type="name",
            name="Test Object",
            auto_route=False,
            proper_motion_aware=True,
            match_epoch=datetime(2015, 6, 1),
            astrometric_weight=0.9,
            photometric_weight=0.1,
        )

        await orchestrator.execute_query(request)

        assert matcher.proper_motion_aware is True
        assert matcher.match_epoch == datetime(2015, 6, 1)
        assert matcher.confidence_scorer.astrometric_weight == pytest.approx(0.9)
        assert matcher.confidence_scorer.photometric_weight == pytest.approx(0.1)

    async def test_execute_query_applies_weighting_profile(self):
        """Test orchestrator applies named weighting profile to scorer."""
        matcher = BayesianMatcher()
        orchestrator = AstroBridgeOrchestrator(matcher=matcher)

        request = QueryRequest(
            query_type="name",
            name="Any",
            auto_route=False,
            weighting_profile="photometry_first",
        )

        await orchestrator.execute_query(request)

        assert matcher.confidence_scorer.weighting_profile == "photometry_first"
        assert matcher.confidence_scorer.astrometric_weight == pytest.approx(0.4)
        assert matcher.confidence_scorer.photometric_weight == pytest.approx(0.6)


class TestSourceConversion:
    """Test source model conversion."""
    
    def test_source_to_response_conversion(self):
        """Test converting Source model to response."""
        from datetime import datetime

        from astrobridge.models import Coordinate, Photometry, Provenance, Source
        
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="TEST"
        )
        
        source = Source(
            id="test-1",
            name="Test Star",
            coordinate=Coordinate(ra=180.0, dec=45.0),
            uncertainty=__import__("astrobridge.models", fromlist=["Uncertainty"]).Uncertainty(
                ra_error=0.5, dec_error=0.5
            ),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov
        )
        
        orchestrator = AstroBridgeOrchestrator()
        response = orchestrator._source_to_response(source, "simbad")
        
        assert response.id == "test-1"
        assert response.name == "Test Star"
        assert response.ra == 180.0
        assert response.dec == 45.0
        assert response.catalog == "simbad"
        assert response.magnitude == 10.0


class TestCrosMatching:
    """Test cross-matching in orchestration (stubbed)."""
    
    def test_cross_match_empty_sources(self):
        """Test cross-match with no sources."""
        orchestrator = AstroBridgeOrchestrator(matcher=BayesianMatcher())
        matches = orchestrator._cross_match_sources([])
        assert matches == []
    
    def test_cross_match_single_source(self):
        """Test cross-match with single source."""
        orchestrator = AstroBridgeOrchestrator(matcher=BayesianMatcher())
        
        source = SourceResponse(
            id="s1", name="Test", ra=180.0, dec=45.0, catalog="simbad"
        )
        matches = orchestrator._cross_match_sources([source])
        assert matches == []
    
    def test_cross_match_no_matcher(self):
        """Test cross-match without matcher."""
        orchestrator = AstroBridgeOrchestrator()
        
        sources = [
            SourceResponse(id="s1", name="Test1", ra=180.0, dec=45.0, catalog="simbad"),
            SourceResponse(id="s2", name="Test2", ra=180.001, dec=45.001, catalog="ned")
        ]
        matches = orchestrator._cross_match_sources(sources)
        assert matches == []
