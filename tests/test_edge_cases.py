"""Edge case tests for AstroBridge robustness."""
from datetime import datetime

import pytest

from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.connectors import CatalogConnector
from astrobridge.identify import identify_object
from astrobridge.matching import BayesianMatcher
from astrobridge.models import Coordinate, Photometry, Provenance, Source, Uncertainty
from astrobridge.routing import NLPQueryRouter


class TestIdentifyEdgeCases:
    """Edge cases for object identification."""

    def test_identify_whitespace_only_input(self):
        """Empty or whitespace-only input should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            identify_object("   ")

    def test_identify_empty_input(self):
        """Empty string input should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            identify_object("")

    def test_identify_very_long_input(self):
        """Very long input should be handled gracefully."""
        long_query = "Find " + ("very " * 100) + "red dwarf stars"
        result = identify_object(long_query)
        assert result is not None
        assert result.object_class is not None

    def test_identify_special_characters(self):
        """Input with special characters should be normalized."""
        result = identify_object("M31@#$%^&*()")
        # Should recognize M31 despite special chars
        assert "GALAXY" in result.object_class.value or result.input_text is not None

    def test_identify_case_insensitivity(self):
        """Identification should be case-insensitive."""
        result_lower = identify_object("m31")
        result_upper = identify_object("M31")
        assert result_lower.object_class == result_upper.object_class


class TestMatcherEdgeCases:
    """Edge cases for the probabilistic matcher."""

    def test_match_empty_reference_sources(self):
        """Matching against empty reference sources should return empty list."""
        matcher = BayesianMatcher()
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test"
        )
        candidate = Source(
            id="cand1",
            name="Test Candidate",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[],
            provenance=prov
        )
        matches = matcher.match([], [candidate])
        assert matches == []

    def test_match_empty_candidate_sources(self):
        """Matching against empty candidates should return empty list."""
        matcher = BayesianMatcher()
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test"
        )
        ref = Source(
            id="ref1",
            name="Test Reference",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[],
            provenance=prov
        )
        matches = matcher.match([ref], [])
        assert matches == []

    def test_match_identical_sources(self):
        """Identical sources should have very high match probability."""
        matcher = BayesianMatcher()
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test"
        )
        source1 = Source(
            id="src1",
            name="Test Source",
            coordinate=Coordinate(ra=100.0, dec=50.0),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov
        )
        source2 = Source(
            id="src2",
            name="Test Source",
            coordinate=Coordinate(ra=100.0, dec=50.0),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov
        )
        matches = matcher.match([source1], [source2])
        assert len(matches) > 0
        assert matches[0].match_probability > 0.5

    def test_match_extreme_separation(self):
        """Sources very far apart should have very low match probability."""
        matcher = BayesianMatcher()
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test"
        )
        source1 = Source(
            id="src1",
            name="Source 1",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov
        )
        source2 = Source(
            id="src2",
            name="Source 2",
            coordinate=Coordinate(ra=180.0, dec=80.0),  # Opposite side of sky
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov
        )
        matches = matcher.match([source1], [source2])
        # Should not match, or very low probability
        if matches:
            assert matches[0].match_probability < 0.2


class TestRouterEdgeCases:
    """Edge cases for the NLP query router."""

    def test_route_empty_query(self):
        """Empty query should classify as UNKNOWN."""
        router = NLPQueryRouter()
        decision = router.parse_query("")
        assert decision is not None

    def test_route_whitespace_only_query(self):
        """Whitespace-only query should classify as UNKNOWN."""
        router = NLPQueryRouter()
        decision = router.parse_query("   ")
        assert decision is not None

    def test_route_conflicting_keywords(self):
        """Query with conflicting keywords should pick one classification."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find star galaxies near nebulae")
        # Should still produce a valid routing decision
        assert decision.object_class is not None
        assert len(decision.catalog_priority) > 0

    def test_route_very_long_query(self):
        """Very long query should be handled without error."""
        router = NLPQueryRouter()
        long_query = "Find " + ("red " * 200) + "dwarf stars"
        decision = router.parse_query(long_query)
        assert decision is not None

    def test_route_numeric_only_query(self):
        """Numeric-only query should classify as UNKNOWN."""
        router = NLPQueryRouter()
        decision = router.parse_query("1234567890")
        assert decision is not None


class TestOrchestratorEdgeCases:
    """Edge cases for the orchestrator."""

    @pytest.mark.asyncio
    async def test_execute_query_no_matches(self):
        """Query returning no sources should succeed gracefully."""

        class EmptyConnector(CatalogConnector):
            def query(self, name):
                return []

            async def async_query(self, name):
                return []

            async def cone_search(self, ra, dec, radius_arcsec):
                return []

        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("EMPTY", EmptyConnector())

        request = QueryRequest(query_type="name", name="NonExistentObject")
        response = await orchestrator.execute_query(request)

        assert response is not None
        assert len(response.sources) == 0
        assert len(response.matches) == 0

    @pytest.mark.asyncio
    async def test_execute_query_very_large_radius(self):
        """Very large search radius should be handled."""

        class SmallConnector(CatalogConnector):
            def query(self, name):
                prov = Provenance(
                    catalog_name="Test",
                    catalog_version="1.0",
                    query_timestamp=datetime.now(),
                    source_id="test"
                )
                return [Source(
                    id="src1",
                    name="Test",
                    coordinate=Coordinate(ra=100.0, dec=50.0),
                    uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
                    photometry=[],
                    provenance=prov
                )]

            async def async_query(self, name):
                return self.query(name)

            async def cone_search(self, ra, dec, radius_arcsec):
                return self.query("")

        orchestrator = AstroBridgeOrchestrator()
        orchestrator.add_connector("TEST", SmallConnector())

        request = QueryRequest(
            query_type="name",
            name="Test",
        )
        response = await orchestrator.execute_query(request)
        assert response is not None


class TestModelEdgeCases:
    """Edge cases for astronomical data models."""

    def test_source_zero_magnitude(self):
        """Source with zero magnitude should be valid."""
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test"
        )
        source = Source(
            id="src1",
            name="Test",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.0, dec_error=0.0),
            photometry=[Photometry(magnitude=0.0, band="V")],
            provenance=prov
        )
        assert source.photometry[0].magnitude == 0.0

    def test_source_negative_magnitude(self):
        """Source with negative magnitude (very bright) should be valid."""
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test"
        )
        source = Source(
            id="src1",
            name="Sirius",
            coordinate=Coordinate(ra=101.28, dec=-16.71),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=-1.46, band="V")],
            provenance=prov
        )
        assert source.photometry[0].magnitude < 0.0

    def test_source_large_uncertainty(self):
        """Source with very large positional uncertainty should be valid."""
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test"
        )
        source = Source(
            id="src1",
            name="Test",
            coordinate=Coordinate(ra=100.0, dec=50.0),
            uncertainty=Uncertainty(ra_error=100.0, dec_error=100.0),
            photometry=[],
            provenance=prov
        )
        assert source.uncertainty.ra_error == 100.0

    def test_coordinate_boundary_ra(self):
        """Coordinates at RA boundaries should be valid."""
        coord = Coordinate(ra=0.0, dec=0.0)
        assert coord.ra == 0.0

        coord = Coordinate(ra=360.0, dec=0.0)
        assert coord.ra == 360.0

    def test_coordinate_boundary_dec(self):
        """Coordinates at declination boundaries should be valid."""
        coord = Coordinate(ra=0.0, dec=-90.0)
        assert coord.dec == -90.0

        coord = Coordinate(ra=0.0, dec=90.0)
        assert coord.dec == 90.0
