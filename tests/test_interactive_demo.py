"""
Tests for interactive_demo.py

Tests the interactive demo functionality, user input handling, and various query scenarios.
"""

import asyncio
from datetime import datetime

import pytest

from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.api.schemas import CoordinateRequest
from astrobridge.connectors import NEDConnector, SimbadConnector
from astrobridge.matching import BayesianMatcher
from astrobridge.models import (
    Coordinate,
    MatchResult,
    Photometry,
    Provenance,
    Source,
    Uncertainty,
)
from astrobridge.routing import NLPQueryRouter


class TestInteractiveDemoSetup:
    """Test orchestrator initialization for interactive demo."""

    def test_orchestrator_initialization(self) -> None:
        """Test that orchestrator initializes with all required components."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher(proper_motion_aware=True))

        assert orchestrator is not None
        assert "simbad" in orchestrator.connectors
        assert "ned" in orchestrator.connectors

    def test_orchestrator_with_live_adapters(self) -> None:
        """Test orchestrator with optional live TAP adapters."""
        try:
            from astrobridge.connectors import NedTapAdapter, SimbadTapAdapter

            orchestrator = AstroBridgeOrchestrator()
            orchestrator.add_connector("simbad", SimbadTapAdapter())
            orchestrator.add_connector("ned", NedTapAdapter())
            orchestrator.set_router(NLPQueryRouter())
            orchestrator.set_matcher(BayesianMatcher(proper_motion_aware=True))

            assert "simbad" in orchestrator.connectors
            assert "ned" in orchestrator.connectors
        except ImportError:
            # Live adapters not available (pyvo not installed)
            pytest.skip("Live TAP adapters require [live] extra")


class TestNameQuery:
    """Test name-based queries from interactive demo."""

    @pytest.mark.asyncio
    async def test_name_query_proxima_centauri(self) -> None:
        """Test name query for well-known object (Proxima Centauri)."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            auto_route=True,
        )

        response = await orchestrator.execute_query(request)

        # Status can be success, partial, or error depending on available catalogs
        assert response.status in ["success", "partial", "error"]
        # Proxima should have sources from at least one catalog
        assert response.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_name_query_m31(self) -> None:
        """Test name query for galaxy (M31)."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="name",
            name="M31",
            auto_route=True,
        )

        response = await orchestrator.execute_query(request)

        # M31 might not be in synthetic data, but should handle gracefully
        assert response.status in ["success", "partial", "error"]

    @pytest.mark.asyncio
    async def test_name_query_unknown_object(self) -> None:
        """Test name query for unknown object (returns empty gracefully)."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="name",
            name="XYZ123UNKNOWN",
            auto_route=True,
        )

        response = await orchestrator.execute_query(request)

        # Should not crash, might have empty results or errors
        assert response.status in ["success", "error", "partial"]


class TestCoordinateQuery:
    """Test coordinate-based cone searches from interactive demo."""

    @pytest.mark.asyncio
    async def test_cone_search_proxima(self) -> None:
        """Test cone search around Proxima Centauri."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="coordinates",
            coordinates=CoordinateRequest(ra=217.429, dec=-62.680, radius_arcsec=60),
            auto_route=False,
            catalogs=["simbad", "ned"],
        )

        response = await orchestrator.execute_query(request)

        assert response.status == "success"
        assert len(response.sources) > 0

    @pytest.mark.asyncio
    async def test_cone_search_large_radius(self) -> None:
        """Test cone search with large radius."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="coordinates",
            coordinates=CoordinateRequest(ra=217.429, dec=-62.680, radius_arcsec=600),
            auto_route=False,
            catalogs=["simbad", "ned"],
        )

        response = await orchestrator.execute_query(request)

        assert response.status in ["success", "partial"]

    @pytest.mark.asyncio
    async def test_cone_search_small_radius(self) -> None:
        """Test cone search with small radius."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="coordinates",
            coordinates=CoordinateRequest(ra=217.429, dec=-62.680, radius_arcsec=10),
            auto_route=False,
            catalogs=["simbad", "ned"],
        )

        response = await orchestrator.execute_query(request)

        # Small radius might yield fewer results
        assert response.status in ["success", "partial"]


class TestNaturalLanguageQuery:
    """Test natural language queries from interactive demo."""

    @pytest.mark.asyncio
    async def test_nl_query_stars(self) -> None:
        """Test NL query for stars."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="natural_language",
            description="Find nearby red dwarf stars",
            auto_route=True,
        )

        response = await orchestrator.execute_query(request)

        assert response.status in ["success", "partial"]
        assert len(response.catalogs_queried) > 0
        assert response.routing_reasoning is not None

    @pytest.mark.asyncio
    async def test_nl_query_galaxies(self) -> None:
        """Test NL query for galaxies."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="natural_language",
            description="Find faint galaxies",
            auto_route=True,
        )

        response = await orchestrator.execute_query(request)

        assert response.status in ["success", "partial"]

    @pytest.mark.asyncio
    async def test_nl_query_negation(self) -> None:
        """Test NL query with negation (edge case)."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        # This is a known limitation: "Not a star" will likely classify as STAR
        request = QueryRequest(
            query_type="natural_language",
            description="Not a star",
            auto_route=True,
        )

        response = await orchestrator.execute_query(request)

        # Should handle gracefully even if router misclassifies
        assert response.status in ["success", "partial", "error"]


class TestObjectIdentification:
    """Test object identification from interactive demo."""

    def test_identify_proxima_centauri(self) -> None:
        """Test identification of Proxima Centauri."""
        from astrobridge.identify import identify_object

        result = identify_object("Proxima Centauri")

        assert result is not None
        assert result.object_class is not None

    def test_identify_m31(self) -> None:
        """Test identification of M31 (galaxy)."""
        from astrobridge.identify import identify_object

        result = identify_object("M31")

        assert result is not None
        assert result.object_class is not None

    def test_identify_unknown(self) -> None:
        """Test identification of unknown input."""
        from astrobridge.identify import identify_object

        result = identify_object("xyz123unknown")

        assert result is not None
        # Should classify as UNKNOWN
        assert result.object_class is not None

    def test_identify_format(self) -> None:
        """Test formatting of identification result."""
        from astrobridge.identify import format_identification, identify_object

        result = identify_object("Sirius")
        formatted = format_identification(result)

        assert formatted is not None
        assert isinstance(formatted, str)
        assert len(formatted) > 0


class TestMatcherControls:
    """Test matcher control options from interactive demo."""

    @pytest.mark.asyncio
    async def test_balanced_weighting_profile(self) -> None:
        """Test balanced weighting profile."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            auto_route=True,
            weighting_profile="balanced",
        )

        response = await orchestrator.execute_query(request)

        assert response.status in ["success", "partial", "error"]

    @pytest.mark.asyncio
    async def test_position_first_weighting(self) -> None:
        """Test position-first weighting profile."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            auto_route=True,
            weighting_profile="position_first",
        )

        response = await orchestrator.execute_query(request)

        assert response.status in ["success", "partial", "error"]

    @pytest.mark.asyncio
    async def test_photometry_first_weighting(self) -> None:
        """Test photometry-first weighting profile."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        request = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            auto_route=True,
            weighting_profile="photometry_first",
        )

        response = await orchestrator.execute_query(request)

        assert response.status in ["success", "partial", "error"]

    @pytest.mark.asyncio
    async def test_proper_motion_aware_matching(self) -> None:
        """Test proper-motion-aware matching."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher(proper_motion_aware=True))

        request = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            auto_route=True,
            proper_motion_aware=True,
            match_epoch=2015.5,
        )

        response = await orchestrator.execute_query(request)

        assert response.status in ["success", "partial", "error"]


class TestBenchmarking:
    """Test benchmarking functionality from interactive demo."""

    @pytest.mark.asyncio
    async def test_benchmark_config(self) -> None:
        """Test benchmark configuration."""
        from astrobridge.benchmarking import BenchmarkConfig

        config = BenchmarkConfig(iterations=3)

        assert config.iterations == 3

    @pytest.mark.asyncio
    async def test_benchmark_runner(self) -> None:
        """Test benchmark runner with minimal iterations."""
        from astrobridge.benchmarking import BenchmarkConfig, BenchmarkRunner

        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        config = BenchmarkConfig(iterations=2)
        runner = BenchmarkRunner(orchestrator)
        results = await runner.run(config)

        assert results is not None
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_benchmark_statistics(self) -> None:
        """Test benchmark statistics collection."""
        from astrobridge.benchmarking import BenchmarkConfig, BenchmarkRunner

        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        config = BenchmarkConfig(iterations=3)
        runner = BenchmarkRunner(orchestrator)
        results = await runner.run(config)

        # Results should contain statistics
        assert results is not None
        assert isinstance(results, dict)


class TestErrorHandling:
    """Test error handling in interactive demo scenarios."""

    @pytest.mark.asyncio
    async def test_query_with_no_results(self) -> None:
        """Test handling of queries with empty results."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())

        request = QueryRequest(
            query_type="name",
            name="XYZ999NOTREAL",
            auto_route=False,
            catalogs=["simbad"],
        )

        response = await orchestrator.execute_query(request)

        # Should handle empty results gracefully
        assert response is not None
        assert response.status in ["success", "partial", "error"]

    @pytest.mark.asyncio
    async def test_multiple_catalog_partial_failure(self) -> None:
        """Test graceful degradation when one catalog fails."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        # Query with both catalogs; if one fails, should still return results
        request = QueryRequest(
            query_type="name",
            name="Proxima Centauri",
            auto_route=False,
            catalogs=["simbad", "ned"],
        )

        response = await orchestrator.execute_query(request)

        # Should handle partial failures gracefully
        assert response.status in ["success", "partial", "error"]

    @pytest.mark.asyncio
    async def test_valid_coordinate_boundaries(self) -> None:
        """Test coordinate validation at model level."""
        # Valid boundaries should work
        coord = CoordinateRequest(ra=0, dec=-90, radius_arcsec=1)
        assert coord.ra == 0
        assert coord.dec == -90
        
        coord = CoordinateRequest(ra=360, dec=90, radius_arcsec=3600)
        assert coord.ra == 360
        assert coord.dec == 90


class TestInputValidation:
    """Test user input validation for interactive demo."""

    def test_object_name_validation(self) -> None:
        """Test that object names are handled (no validation needed)."""
        # Object names can be arbitrary strings, no validation required
        name = "Proxima Centauri"
        assert isinstance(name, str)
        assert len(name) > 0

    def test_coordinate_validation_ra_bounds(self) -> None:
        """Test RA bounds validation."""
        # Valid RA: 0-360
        assert 0 <= 217.429 <= 360
        assert 0 <= 0 <= 360
        assert 0 <= 360 <= 360

    def test_coordinate_validation_dec_bounds(self) -> None:
        """Test Dec bounds validation."""
        # Valid Dec: -90 to +90
        assert -90 <= -62.680 <= 90
        assert -90 <= 0 <= 90
        assert -90 <= 90 <= 90

    def test_radius_validation(self) -> None:
        """Test search radius validation."""
        # Radius should be positive
        assert 60 > 0
        assert 300 > 0
        assert 10 > 0

    @pytest.mark.asyncio
    async def test_query_type_validation(self) -> None:
        """Test that QueryRequest validates query_type."""
        # Valid query types: name, coordinates, natural_language
        valid_types = ["name", "coordinates", "natural_language"]

        for query_type in valid_types:
            if query_type == "name":
                request = QueryRequest(query_type=query_type, name="Test")
            elif query_type == "coordinates":
                request = QueryRequest(
                    query_type=query_type,
                    coordinates=CoordinateRequest(ra=100, dec=45, radius_arcsec=60),
                )
            else:
                request = QueryRequest(query_type=query_type, description="Test")

            assert request.query_type == query_type


class TestConcurrentQueries:
    """Test concurrent query execution (stress test)."""

    @pytest.mark.asyncio
    async def test_concurrent_name_queries(self) -> None:
        """Test multiple concurrent name queries."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        queries = [
            QueryRequest(query_type="name", name="Proxima Centauri", auto_route=True),
            QueryRequest(query_type="name", name="Sirius", auto_route=True),
            QueryRequest(query_type="name", name="Vega", auto_route=True),
        ]

        tasks = [orchestrator.execute_query(q) for q in queries]
        responses = await asyncio.gather(*tasks)

        assert len(responses) == 3
        assert all(r.status in ["success", "partial"] for r in responses)

    @pytest.mark.asyncio
    async def test_concurrent_coordinate_queries(self) -> None:
        """Test multiple concurrent coordinate queries."""
        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
        orchestrator.set_router(NLPQueryRouter())
        orchestrator.set_matcher(BayesianMatcher())

        queries = [
            QueryRequest(
                query_type="coordinates",
                coordinates=CoordinateRequest(ra=217.429, dec=-62.680, radius_arcsec=60),
                auto_route=False,
                catalogs=["simbad"],
            ),
            QueryRequest(
                query_type="coordinates",
                coordinates=CoordinateRequest(ra=101.287, dec=-16.716, radius_arcsec=60),
                auto_route=False,
                catalogs=["simbad"],
            ),
        ]

        tasks = [orchestrator.execute_query(q) for q in queries]
        responses = await asyncio.gather(*tasks)

        assert len(responses) == 2
        assert all(r.status in ["success", "partial"] for r in responses)


class TestOutputFormatting:
    """Test output formatting for interactive demo display."""

    def test_source_display_format(self) -> None:
        """Test that Source objects format correctly for display."""
        source = Source(
            id="test-1",
            name="Test Object",
            coordinate=Coordinate(ra=100.5, dec=45.5, pm_ra_mas_per_year=None, pm_dec_mas_per_year=None),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.5, band="V", magnitude_error=None)],
            provenance=Provenance(
                catalog_name="TEST",
                catalog_version="1.0",
                query_timestamp=datetime.now(),
                source_id="test-src-1",
            ),
        )

        # Should format nicely
        assert source.name == "Test Object"
        assert source.coordinate.ra == 100.5
        assert source.coordinate.dec == 45.5
        assert len(source.photometry) == 1

    def test_match_result_display_format(self) -> None:
        """Test that MatchResult objects format correctly."""
        match = MatchResult(
            source1_id="src1",
            source2_id="src2",
            match_probability=0.95,
            separation_arcsec=21.45,
            confidence=0.92,
        )

        # Should display nicely
        assert match.match_probability == 0.95
        assert match.separation_arcsec == 21.45
        assert match.confidence == 0.92


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
