"""Tests for confidence scoring in source matching."""
import pytest
from datetime import datetime
from astrobridge.models import Source, Coordinate, Uncertainty, Photometry, Provenance, MatchResult
from astrobridge.matching.confidence import ConfidenceScorer, MatchScore


@pytest.fixture
def provenance_simbad():
    """Create SIMBAD provenance."""
    return Provenance(
        catalog_name="SIMBAD",
        catalog_version="2026.04",
        query_timestamp=datetime.now(),
        source_id="simbad_123"
    )


@pytest.fixture
def provenance_ned():
    """Create NED provenance."""
    return Provenance(
        catalog_name="NED",
        catalog_version="2025.10",
        query_timestamp=datetime.now(),
        source_id="ned_456"
    )


def create_source(ra, dec, ra_err=0.5, dec_err=0.5, name="test_source", provenance=None):
    """Helper to create a source."""
    if provenance is None:
        provenance = Provenance(
            catalog_name="TEST",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test_123"
        )
    return Source(
        id=f"test_{ra}_{dec}",
        name=name,
        coordinate=Coordinate(ra=ra, dec=dec),
        uncertainty=Uncertainty(ra_error=ra_err, dec_error=dec_err),
        photometry=[],
        provenance=provenance
    )


class TestConfidenceScorerBasic:
    """Test basic confidence scoring logic."""
    
    def test_perfect_match_high_confidence(self):
        """Perfect match (same position, small uncertainty) should score high."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, ra_err=0.1, dec_err=0.1, name="Obj A")
        source2 = create_source(10.0, 20.0, ra_err=0.1, dec_err=0.1, name="Obj B")
        
        score = scorer.compute_score(source1, source2, separation_arcsec=0.05)
        
        # Perfect match with tiny separation should score >= 0.95
        assert score.confidence >= 0.95
        assert score.confidence <= 1.0
        assert "separation" in score.explanation
        assert "low" in score.explanation.lower()
    
    def test_ambiguous_match_lower_confidence(self):
        """Ambiguous match (moderate separation) should score lower."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, ra_err=0.5, dec_err=0.5, name="Obj A")
        source2 = create_source(10.05, 20.0, ra_err=0.5, dec_err=0.5, name="Obj B")
        
        # ~180 arcsec separation
        score = scorer.compute_score(source1, source2, separation_arcsec=180.0)
        
        # Moderate separation should score lower
        assert score.confidence < 0.8
        assert score.confidence >= 0.3
    
    def test_poor_match_low_confidence(self):
        """Poor match (large separation) should score low."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, ra_err=0.5, dec_err=0.5, name="Obj A")
        source2 = create_source(10.5, 20.5, ra_err=0.5, dec_err=0.5, name="Obj B")
        
        # ~700 arcsec separation
        score = scorer.compute_score(source1, source2, separation_arcsec=700.0)
        
        # Large separation should score low
        assert score.confidence < 0.4
    
    def test_high_uncertainty_reduces_confidence(self):
        """High astrometric uncertainty should allow for larger separations."""
        scorer = ConfidenceScorer()
        
        # Scenario 1: Small uncertainties, small separation
        source1a = create_source(10.0, 20.0, ra_err=0.1, dec_err=0.1, name="Src1")
        source2a = create_source(10.01, 20.0, ra_err=0.1, dec_err=0.1, name="Src2")
        score1 = scorer.compute_score(source1a, source2a, separation_arcsec=36.0)  # 36 arcsec
        
        # Scenario 2: Large uncertainties, same separation
        source1b = create_source(10.0, 20.0, ra_err=2.0, dec_err=2.0, name="Src1")
        source2b = create_source(10.01, 20.0, ra_err=2.0, dec_err=2.0, name="Src2")
        score2 = scorer.compute_score(source1b, source2b, separation_arcsec=36.0)
        
        # High-uncertainty match should score higher for same separation
        assert score2.confidence >= score1.confidence


class TestConfidenceScorerWithPhotometry:
    """Test confidence scoring with photometric data."""
    
    def test_photometric_consistency_improves_score(self):
        """Consistent photometry should improve match confidence."""
        scorer = ConfidenceScorer()
        
        prov = Provenance(catalog_name="TEST", catalog_version="1.0", 
                         query_timestamp=datetime.now(), source_id="test")
        
        # Source with photometry
        source1 = Source(
            id="src1", name="Obj1",
            coordinate=Coordinate(ra=10.0, dec=20.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=15.0, band="V", magnitude_error=0.1)],
            provenance=prov
        )
        
        source2 = Source(
            id="src2", name="Obj2",
            coordinate=Coordinate(ra=10.01, dec=20.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=15.05, band="V", magnitude_error=0.1)],
            provenance=prov
        )
        
        score = scorer.compute_score(source1, source2, separation_arcsec=36.0)
        
        # Should have photometric factor in explanation
        assert "photometric" in score.explanation.lower()
        assert score.confidence > 0.0
    
    def test_photometric_inconsistency_reduces_score(self):
        """Inconsistent photometry should reduce match confidence."""
        scorer = ConfidenceScorer()
        
        prov = Provenance(catalog_name="TEST", catalog_version="1.0",
                         query_timestamp=datetime.now(), source_id="test")
        
        # Very different magnitudes
        source1 = Source(
            id="src1", name="Obj1",
            coordinate=Coordinate(ra=10.0, dec=20.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=10.0, band="V", magnitude_error=0.1)],
            provenance=prov
        )
        
        source2 = Source(
            id="src2", name="Obj2",
            coordinate=Coordinate(ra=10.01, dec=20.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=18.0, band="V", magnitude_error=0.1)],
            provenance=prov
        )
        
        score = scorer.compute_score(source1, source2, separation_arcsec=36.0)
        
        # Very different magnitudes should reduce confidence
        assert score.confidence < 0.3


class TestMatchScoreStructure:
    """Test MatchScore result structure."""
    
    def test_match_score_has_required_fields(self):
        """MatchScore should have all required explanation fields."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, name="Obj A")
        source2 = create_source(10.001, 20.0, name="Obj B")
        
        score = scorer.compute_score(source1, source2, separation_arcsec=3.6)
        
        # Check structure
        assert isinstance(score.confidence, float)
        assert 0.0 <= score.confidence <= 1.0
        assert isinstance(score.explanation, str)
        assert len(score.explanation) > 0
        assert "separation" in score.explanation.lower() or "astrometric" in score.explanation.lower()
    
    def test_match_score_explanation_is_readable(self):
        """MatchScore explanation should be human-readable."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, name="Obj A")
        source2 = create_source(10.01, 20.0, name="Obj B")
        
        score = scorer.compute_score(source1, source2, separation_arcsec=36.0)
        
        # Explanation should be human-readable
        assert len(score.explanation) > 10
        assert any(char.isupper() for char in score.explanation)  # Has capital letters


class TestConfidenceScorerEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_separation_max_confidence(self):
        """Zero separation should give maximum confidence."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, ra_err=0.1, dec_err=0.1)
        source2 = create_source(10.0, 20.0, ra_err=0.1, dec_err=0.1)
        
        score = scorer.compute_score(source1, source2, separation_arcsec=0.0)
        
        assert score.confidence > 0.98
    
    def test_very_large_separation_near_zero_confidence(self):
        """Very large separation should give near-zero confidence."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, ra_err=0.5, dec_err=0.5)
        source2 = create_source(11.0, 21.0, ra_err=0.5, dec_err=0.5)
        
        # ~5000 arcsec separation
        score = scorer.compute_score(source1, source2, separation_arcsec=5000.0)
        
        assert score.confidence < 0.05
    
    def test_scores_are_deterministic(self):
        """Same inputs should give same scores."""
        scorer = ConfidenceScorer()
        
        source1 = create_source(10.0, 20.0, name="Obj A")
        source2 = create_source(10.01, 20.0, name="Obj B")
        
        score1 = scorer.compute_score(source1, source2, separation_arcsec=36.0)
        score2 = scorer.compute_score(source1, source2, separation_arcsec=36.0)
        
        assert score1.confidence == score2.confidence
        assert score1.explanation == score2.explanation


class TestConfidenceProfiles:
    """Test weighting profile behavior."""

    def test_from_profile_assigns_expected_weights(self):
        scorer = ConfidenceScorer.from_profile("position_first")
        assert scorer.astrometric_weight == pytest.approx(0.9)
        assert scorer.photometric_weight == pytest.approx(0.1)
        assert scorer.weighting_profile == "position_first"

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError):
            ConfidenceScorer.from_profile("not_a_profile")

    def test_profile_changes_confidence_for_photometric_conflict(self):
        prov = Provenance(
            catalog_name="TEST",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="test",
        )

        source1 = Source(
            id="src1",
            name="Obj1",
            coordinate=Coordinate(ra=10.0, dec=20.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=10.0, band="V", magnitude_error=0.1)],
            provenance=prov,
        )
        source2 = Source(
            id="src2",
            name="Obj2",
            coordinate=Coordinate(ra=10.01, dec=20.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=18.0, band="V", magnitude_error=0.1)],
            provenance=prov,
        )

        position_first = ConfidenceScorer.from_profile("position_first")
        photometry_first = ConfidenceScorer.from_profile("photometry_first")

        s_pos = position_first.compute_score(source1, source2, separation_arcsec=36.0)
        s_photo = photometry_first.compute_score(source1, source2, separation_arcsec=36.0)

        assert s_pos.confidence > s_photo.confidence
