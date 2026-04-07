"""Unit tests for probabilistic matcher."""
import pytest
import numpy as np
from datetime import datetime
from astrobridge.matching import BayesianMatcher, MatcherConfig, ObjectType
from astrobridge.models import (
    Source, Coordinate, Uncertainty, Photometry, Provenance
)


@pytest.fixture
def sample_sources():
    """Create sample sources for testing."""
    prov = Provenance(
        catalog_name="Test",
        catalog_version="1.0",
        query_timestamp=datetime.now(),
        source_id="TEST"
    )
    
    source1 = Source(
        id="src-1",
        name="Object1",
        coordinate=Coordinate(ra=180.0, dec=45.0),
        uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),  # Realistic 0.5 arcsec
        photometry=[Photometry(magnitude=10.0, band="V")],
        provenance=prov
    )
    
    source2 = Source(
        id="src-2",
        name="Object2",
        coordinate=Coordinate(ra=180.0002777778, dec=45.0002777778),  # 1 arcsec away
        uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),  # Realistic 0.5 arcsec
        photometry=[Photometry(magnitude=10.1, band="V")],
        provenance=prov
    )
    
    source3 = Source(
        id="src-3",
        name="Object3",
        coordinate=Coordinate(ra=190.0, dec=50.0),  # Far away
        uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),  # Realistic 0.5 arcsec
        photometry=[Photometry(magnitude=12.0, band="V")],
        provenance=prov
    )
    
    return [source1, source2, source3]


class TestBayesianMatcher:
    """Test BayesianMatcher implementation."""
    
    def test_matcher_initialization(self):
        """Test matcher initialization with defaults."""
        matcher = BayesianMatcher()
        assert matcher.positional_sigma_threshold == 3.0
        assert matcher.confidence_threshold == 0.05
        assert matcher.prior_match_prob == 0.7
    
    def test_set_thresholds(self):
        """Test setting matcher thresholds."""
        matcher = BayesianMatcher()
        matcher.set_thresholds(confidence_threshold=0.7, positional_sigma_threshold=2.5)
        assert matcher.confidence_threshold == 0.7
        assert matcher.positional_sigma_threshold == 2.5
    
    def test_invalid_confidence_threshold(self):
        """Test invalid confidence threshold."""
        matcher = BayesianMatcher()
        with pytest.raises(ValueError):
            matcher.set_thresholds(confidence_threshold=1.5)
    
    def test_match_probability_calculation(self, sample_sources):
        """Test match probability calculation."""
        matcher = BayesianMatcher()
        
        # Close sources should have higher probability than far sources
        prob_close = matcher.calculate_match_probability(sample_sources[0], sample_sources[1])
        prob_far = matcher.calculate_match_probability(sample_sources[0], sample_sources[2])
        
        assert prob_close > prob_far
        assert prob_close > 0.05  # Close sources should have non-trivial probability
    
    def test_match_execution(self, sample_sources):
        """Test full matching execution."""
        matcher = BayesianMatcher()
        
        ref_sources = [sample_sources[0]]
        candidates = [sample_sources[1], sample_sources[2]]
        
        matches = matcher.match(ref_sources, candidates)
        
        # Should find one match (to closer source)
        assert len(matches) > 0
        assert matches[0].source1_id == "src-1"
        assert matches[0].source2_id == "src-2"
    
    def test_calibration_metrics(self, sample_sources):
        """Test calibration metrics."""
        matcher = BayesianMatcher()
        matcher.set_calibration_metrics(accuracy=0.95, precision=0.92, recall=0.88)
        
        metrics = matcher.get_calibration_metrics()
        assert metrics["accuracy"] == 0.95
        assert metrics["precision"] == 0.92
        assert metrics["recall"] == 0.88


class TestMatcherConfig:
    """Test matcher configuration."""
    
    def test_config_initialization(self):
        """Test config initialization with object type."""
        config = MatcherConfig(ObjectType.STAR)
        assert config.object_type == ObjectType.STAR
    
    def test_config_parameters(self):
        """Test getting/setting configuration parameters."""
        config = MatcherConfig(ObjectType.GALAXY)
        
        # Get default
        sigma = config.get_param("positional_sigma_threshold")
        assert sigma == 3.0
        
        # Set new value
        config.set_param("positional_sigma_threshold", 2.5)
        assert config.get_param("positional_sigma_threshold") == 2.5
    
    def test_starconfig_different_from_galaxy(self):
        """Test that star and galaxy configs differ."""
        star_config = MatcherConfig(ObjectType.STAR)
        galaxy_config = MatcherConfig(ObjectType.GALAXY)
        
        star_sigma = star_config.get_param("positional_sigma_threshold")
        galaxy_sigma = galaxy_config.get_param("positional_sigma_threshold")
        
        assert star_sigma != galaxy_sigma


class TestMatcherCalibration:
    """Test calibration utilities."""
    
    def test_evaluate_matches(self):
        """Test match evaluation."""
        from astrobridge.matching import MatcherCalibrator
        from astrobridge.models import MatchResult
        
        # Create matches
        matches = [
            MatchResult(
                source1_id="ref1",
                source2_id="cand1",
                match_probability=0.9,
                separation_arcsec=5.4,
                confidence=0.9
            ),
            MatchResult(
                source1_id="ref2",
                source2_id="cand2",
                match_probability=0.7,
                separation_arcsec=7.2,
                confidence=0.7
            )
        ]
        
        # Ground truth
        truth = [("ref1", "cand1"), ("ref2", "cand3")]
        
        metrics = MatcherCalibrator.evaluate_matches(matches, truth)
        
        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert metrics["true_positives"] == 1
        assert metrics["false_positives"] == 1
        assert metrics["false_negatives"] == 1
