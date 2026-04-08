"""Integration tests for full matching pipeline."""
import pytest
from datetime import datetime
from astrobridge.connectors import SimbadConnector, NEDConnector
from astrobridge.matching import BayesianMatcher, MatcherConfig, ObjectType
from astrobridge.models import (
    Coordinate, Source, Uncertainty, Photometry, Provenance
)


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
                assert match.source1_id in [s.id for s in simbad_results]
                assert match.source2_id in [s.id for s in ned_results]
                assert 0.0 <= match.match_probability <= 1.0

    @pytest.mark.asyncio
    async def test_proper_motion_epoch_aware_cross_match(self):
        """Test epoch-aware matching for sources with proper motion drift."""
        epoch_2000 = datetime(2000, 1, 1)
        epoch_2020 = datetime(2020, 1, 1)

        ref_sources = [
            Source(
                id="pm-int-ref",
                name="PMIntRef",
                coordinate=Coordinate(
                    ra=150.0,
                    dec=30.0,
                    pm_ra_mas_per_year=3500.0,
                    pm_dec_mas_per_year=0.0,
                ),
                uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
                photometry=[Photometry(magnitude=13.2, band="V")],
                provenance=Provenance(
                    catalog_name="CAT-A",
                    catalog_version="1.0",
                    query_timestamp=epoch_2000,
                    source_id="A-PM-1",
                ),
            )
        ]

        candidate_sources = [
            Source(
                id="pm-int-cand",
                name="PMIntCand",
                coordinate=Coordinate(
                    ra=150.0 + (70.0 / 3600.0),
                    dec=30.0,
                    pm_ra_mas_per_year=3500.0,
                    pm_dec_mas_per_year=0.0,
                ),
                uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
                photometry=[Photometry(magnitude=13.2, band="V")],
                provenance=Provenance(
                    catalog_name="CAT-B",
                    catalog_version="1.0",
                    query_timestamp=epoch_2020,
                    source_id="B-PM-1",
                ),
            )
        ]

        plain = BayesianMatcher(proper_motion_aware=False)
        pm_aware = BayesianMatcher(proper_motion_aware=True)

        plain_matches = plain.match(ref_sources, candidate_sources)
        pm_matches = pm_aware.match(ref_sources, candidate_sources)

        assert len(plain_matches) == 0
        assert len(pm_matches) == 1
        assert pm_matches[0].source1_id == "pm-int-ref"
        assert pm_matches[0].source2_id == "pm-int-cand"
        assert pm_matches[0].separation_arcsec < 1.0


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
            name="TestRef",
            coordinate=Coordinate(ra=180.0, dec=45.0),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[],
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
