"""Regression tests for deterministic matching output."""
import pytest
from datetime import datetime
from astrobridge.matching import BayesianMatcher
from astrobridge.models import (
    Source, Coordinate, Uncertainty, Photometry, Provenance
)


@pytest.fixture
def fixed_sources():
    """Create fixed test sources with deterministic values."""
    prov = Provenance(
        catalog_name="RegTest",
        catalog_version="1.0",
        query_timestamp=datetime(2024, 1, 1, 12, 0, 0),
        source_id="FIXED"
    )
    
    sources = []
    for i in range(5):
        source = Source(
            id=f"fixed-{i}",
            name=f"FixedObject{i}",
            coordinate=Coordinate(ra=180.0 + i*0.01, dec=45.0 + i*0.01),
            uncertainty=Uncertainty(ra_error=0.05, dec_error=0.05, ra_dec_correlation=0.0),
            photometry=[Photometry(magnitude=10.0 + i*0.5, band="V")],
            provenance=prov
        )
        sources.append(source)
    
    return sources


class TestMatchingDeterminism:
    """Test that matching produces deterministic results."""
    
    def test_same_input_same_output(self, fixed_sources):
        """Test that identical inputs produce identical results."""
        matcher = BayesianMatcher(
            positional_sigma_threshold=3.0,
            confidence_threshold=0.5,
            prior_match_prob=0.1
        )
        
        ref = [fixed_sources[0]]
        cand = fixed_sources[1:]
        
        # Run twice
        result1 = matcher.match(ref, cand)
        result2 = matcher.match(ref, cand)
        
        # Should have same matches
        assert len(result1) == len(result2)
        for m1, m2 in zip(result1, result2):
            assert m1.source_ref == m2.source_ref
            assert m1.source_match == m2.source_match
            assert abs(m1.match_probability - m2.match_probability) < 1e-10
    
    def test_match_probability_bounds(self, fixed_sources):
        """Test that probabilities stay in [0, 1] range."""
        matcher = BayesianMatcher()
        
        ref = [fixed_sources[0]]
        cand = fixed_sources[1:]
        
        matches = matcher.match(ref, cand)
        
        for match in matches:
            assert 0.0 <= match.match_probability <= 1.0
            assert match.position_significance >= 0.0
            assert 0.0 <= match.photometric_consistency <= 1.0
    
    def test_significance_ordering(self, fixed_sources):
        """Test that closer sources have higher match probability."""
        matcher = BayesianMatcher()
        
        # Source 0 should match better to source 1 (closer) than source 4 (farther)
        prob_close = matcher.calculate_match_probability(fixed_sources[0], fixed_sources[1])
        prob_far = matcher.calculate_match_probability(fixed_sources[0], fixed_sources[4])
        
        assert prob_close > prob_far
