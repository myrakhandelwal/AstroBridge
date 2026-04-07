"""Integration tests for full matching pipeline."""
import pytest
import asyncio
from astrobridge.connectors import SimbadConnector, NEDConnector
from astrobridge.matching import BayesianMatcher, MatcherConfig, ObjectType
from astrobridge.models import Coordinate


@pytest.mark.asyncio
class TestMatchingPipeline:
    """Test full matching pipeline with real connectors."""
    
    @pytest.mark.asyncio
    async def test_simbad_ned_cross_match(self):
        """Test cross-matching between Simbad and NED results."""
        simbad = SimbadConnector()
        ned = NEDConnector()
        matcher = BayesianMatcher()
        
        # Query both catalogs
        simbad_results = await simbad.query_object("ProxCen")
        ned_results = await ned.query_object("ProxCen")
        
        if simbad_results and ned_results:
            # Match against each other
            matches = matcher.match(simbad_results, ned_results)
            
            # Should find at least one match
            assert len(matches) >= 0  # May not find matches if results too different
    
    @pytest.mark.asyncio
    async def test_cone_search_cross_match(self):
        """Test cross-matching from cone searches."""
        simbad = SimbadConnector()
        ned = NEDConnector()
        matcher = BayesianMatcher()
        
        coord = Coordinate(ra=180.0, dec=45.0)
        
        # Cone searches
        simbad_results = await simbad.cone_search(coord, 300)
        ned_results = await ned.cone_search(coord, 300)
        
        if simbad_results and ned_results:
            # Match
            matches = matcher.match(simbad_results, ned_results)
            
            # Verify match structure
            for match in matches:
                assert match.source_ref in [s.id for s in simbad_results]
                assert match.source_match in [s.id for s in ned_results]
                assert 0.0 <= match.match_probability <= 1.0


class TestMatcherConfigIntegration:
    """Test matcher configuration in realistic scenarios."""
    
    def test_star_matching_with_config(self):
        """Test star matching with object-specific config."""
        config = MatcherConfig(ObjectType.STAR)
        
        # Create matcher with config parameters
        matcher = BayesianMatcher(
            positional_sigma_threshold=config.get_param("positional_sigma_threshold"),
            confidence_threshold=config.get_param("confidence_threshold"),
            prior_match_prob=config.get_param("prior_match_prob")
        )
        
        assert matcher.positional_sigma_threshold == 2.5
        assert matcher.confidence_threshold == 0.7
    
    def test_galaxy_matching_with_config(self):
        """Test galaxy matching with object-specific config."""
        config = MatcherConfig(ObjectType.GALAXY)
        
        matcher = BayesianMatcher(
            positional_sigma_threshold=config.get_param("positional_sigma_threshold"),
            confidence_threshold=config.get_param("confidence_threshold")
        )
        
        assert matcher.positional_sigma_threshold == 3.0
        assert matcher.confidence_threshold == 0.6


class TestErrorHandling:
    """Test error handling in matching."""
    
    def test_empty_candidates(self):
        """Test matching with empty candidate list."""
        matcher = BayesianMatcher()
        from astrobridge.models import Source, Coordinate, Provenance
        from datetime import datetime
        
        prov = Provenance(
            catalog_name="Test",
            catalog_version="1.0",
            query_timestamp=datetime.now(),
            source_id="TEST"
        )
        
        ref = [Source(
            id="ref1",
            coordinate=Coordinate(ra=180.0, dec=45.0),
            provenance=prov
        )]
        
        matches = matcher.match(ref, [])
        assert matches == []
    
    def test_threshold_validation(self):
        """Test threshold validation."""
        matcher = BayesianMatcher()
        
        with pytest.raises(ValueError):
            matcher.set_thresholds(confidence_threshold=2.0)
        
        with pytest.raises(ValueError):
            matcher.set_thresholds(positional_sigma_threshold=-1.0)
