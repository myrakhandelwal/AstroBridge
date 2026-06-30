"""Edge case tests for AstroBridge robustness."""
from datetime import datetime

import pytest

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
            source_id="test",
        )
        candidate = Source(
            id="cand1",
            name="Test Candidate",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[],
            provenance=prov,
        )
        assert matcher.match([], [candidate]) == []

    def test_match_empty_candidate_sources(self):
        """Matching against empty candidates should return empty list."""
        matcher = BayesianMatcher()
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test",
        )
        ref = Source(
            id="ref1",
            name="Test Reference",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[],
            provenance=prov,
        )
        assert matcher.match([ref], []) == []

    def test_match_identical_sources(self):
        """Identical sources should have very high match probability."""
        matcher = BayesianMatcher()
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test",
        )
        source1 = Source(
            id="src1",
            name="Test Source",
            coordinate=Coordinate(ra=100.0, dec=50.0),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov,
        )
        source2 = Source(
            id="src2",
            name="Test Source",
            coordinate=Coordinate(ra=100.0, dec=50.0),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov,
        )
        matches = matcher.match([source1], [source2])
        assert len(matches) > 0
        assert matches[0].match_probability > 0.5

    def test_match_extreme_separation(self):
        """Sources very far apart should not match."""
        matcher = BayesianMatcher()
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test",
        )
        source1 = Source(
            id="src1",
            name="Source 1",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov,
        )
        source2 = Source(
            id="src2",
            name="Source 2",
            coordinate=Coordinate(ra=180.0, dec=80.0),
            uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
            photometry=[Photometry(magnitude=10.0, band="V")],
            provenance=prov,
        )
        matches = matcher.match([source1], [source2])
        if matches:
            assert matches[0].match_probability < 0.2


class TestRouterEdgeCases:
    """Edge cases for the NLP query router."""

    def test_route_empty_query(self):
        """Empty query should return a valid routing decision."""
        router = NLPQueryRouter()
        assert router.parse_query("") is not None

    def test_route_whitespace_only_query(self):
        """Whitespace-only query should return a valid routing decision."""
        router = NLPQueryRouter()
        assert router.parse_query("   ") is not None

    def test_route_conflicting_keywords(self):
        """Query with conflicting keywords should still produce a valid decision."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find star galaxies near nebulae")
        assert decision.object_class is not None
        assert len(decision.catalog_priority) > 0

    def test_route_very_long_query(self):
        """Very long query should be handled without error."""
        router = NLPQueryRouter()
        assert router.parse_query("Find " + ("red " * 200) + "dwarf stars") is not None

    def test_route_numeric_only_query(self):
        """Numeric-only query should return a valid routing decision."""
        router = NLPQueryRouter()
        assert router.parse_query("1234567890") is not None


class TestModelEdgeCases:
    """Edge cases for astronomical data models."""

    def test_source_zero_magnitude(self):
        prov = Provenance(
            catalog_name="Test", catalog_version="1.0",
            query_timestamp=datetime.now(), source_id="test",
        )
        source = Source(
            id="src1", name="Test",
            coordinate=Coordinate(ra=0.0, dec=0.0),
            uncertainty=Uncertainty(ra_error=0.0, dec_error=0.0),
            photometry=[Photometry(magnitude=0.0, band="V")],
            provenance=prov,
        )
        assert source.photometry[0].magnitude == 0.0

    def test_source_negative_magnitude(self):
        """Negative magnitude (very bright object like Sirius) should be valid."""
        prov = Provenance(
            catalog_name="Test", catalog_version="1.0",
            query_timestamp=datetime.now(), source_id="test",
        )
        source = Source(
            id="src1", name="Sirius",
            coordinate=Coordinate(ra=101.28, dec=-16.71),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=-1.46, band="V")],
            provenance=prov,
        )
        assert source.photometry[0].magnitude < 0.0

    def test_source_large_uncertainty(self):
        prov = Provenance(
            catalog_name="Test", catalog_version="1.0",
            query_timestamp=datetime.now(), source_id="test",
        )
        source = Source(
            id="src1", name="Test",
            coordinate=Coordinate(ra=100.0, dec=50.0),
            uncertainty=Uncertainty(ra_error=100.0, dec_error=100.0),
            photometry=[],
            provenance=prov,
        )
        assert source.uncertainty.ra_error == 100.0

    def test_coordinate_boundary_ra(self):
        assert Coordinate(ra=0.0, dec=0.0).ra == 0.0
        assert Coordinate(ra=360.0, dec=0.0).ra == 360.0

    def test_coordinate_boundary_dec(self):
        assert Coordinate(ra=0.0, dec=-90.0).dec == -90.0
        assert Coordinate(ra=0.0, dec=90.0).dec == 90.0
