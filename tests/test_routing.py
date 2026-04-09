"""Tests for intelligent query routing."""
from astrobridge.routing import CatalogRanker, NLPQueryRouter
from astrobridge.routing.base import CatalogType, ObjectClass, RoutingDecision


class TestObjectClassification:
    """Test object classification from natural language."""
    
    def test_classify_star(self):
        """Test star classification."""
        router = NLPQueryRouter()
        
        queries = [
            "Find nearby red dwarf stars",
            "Search for main sequence stars",
            "Look for binary stars",
            "Find a white dwarf"
        ]
        
        for query in queries:
            result = router.classify_object(query)
            assert result == ObjectClass.STAR, f"Failed to classify: {query}"
    
    def test_classify_galaxy(self):
        """Test galaxy classification."""
        router = NLPQueryRouter()
        
        queries = [
            "Find nearby galaxies",
            "Search for spiral galaxies",
            "Look for dwarf galaxies",
            "Find elliptical galaxies"
        ]
        
        for query in queries:
            result = router.classify_object(query)
            assert result == ObjectClass.GALAXY, f"Failed to classify: {query}"
    
    def test_classify_quasar(self):
        """Test quasar classification."""
        router = NLPQueryRouter()
        
        queries = [
            "Find quasars at high redshift",
            "Search for QSOs",
            "Look for quasi-stellar objects"
        ]
        
        for query in queries:
            result = router.classify_object(query)
            assert result == ObjectClass.QUASAR, f"Failed to classify: {query}"
    
    def test_classify_agn(self):
        """Test AGN classification."""
        router = NLPQueryRouter()
        
        queries = [
            "Find active galactic nuclei",
            "Search for Seyfert galaxies",
            "Look for blazars",
            "Find BL Lac objects"
        ]
        
        for query in queries:
            result = router.classify_object(query)
            assert result == ObjectClass.AGN, f"Failed to classify: {query}"
    
    def test_classify_nebula(self):
        """Test nebula classification."""
        router = NLPQueryRouter()
        
        queries = [
            "Find planetary nebulae",
            "Search for emission nebulae",
            "Look for dark clouds",
            "Find HII regions"
        ]
        
        for query in queries:
            result = router.classify_object(query)
            assert result == ObjectClass.NEBULA, f"Failed to classify: {query}"
    
    def test_classify_cluster(self):
        """Test cluster classification."""
        router = NLPQueryRouter()
        
        queries = [
            "Find star clusters",
            "Search for globular clusters",
            "Look for open clusters"
        ]
        
        for query in queries:
            result = router.classify_object(query)
            assert result == ObjectClass.CLUSTER, f"Failed to classify: {query}"
    
    def test_classify_supernova(self):
        """Test supernova classification."""
        router = NLPQueryRouter()
        
        queries = [
            "Find recent supernovae",
            "Search for SN explosions",
            "Look for transient events"
        ]
        
        for query in queries:
            result = router.classify_object(query)
            assert result == ObjectClass.SNE, f"Failed to classify: {query}"
    
    def test_classify_unknown(self):
        """Test unknown object classification."""
        router = NLPQueryRouter()
        result = router.classify_object("Find something in the sky")
        assert result == ObjectClass.UNKNOWN


class TestCatalogRanking:
    """Test catalog ranking for different object types."""
    
    def test_star_ranking(self):
        """Test that Gaia ranks highest for stars."""
        ranking = CatalogRanker.rank_for_class(ObjectClass.STAR)
        top_catalog = ranking[0][0]
        assert top_catalog == CatalogType.GAIA
    
    def test_galaxy_ranking(self):
        """Test that NED ranks highest for galaxies."""
        ranking = CatalogRanker.rank_for_class(ObjectClass.GALAXY)
        top_catalog = ranking[0][0]
        assert top_catalog == CatalogType.NED
    
    def test_quasar_ranking(self):
        """Test that NED ranks high for quasars."""
        ranking = CatalogRanker.rank_for_class(ObjectClass.QUASAR)
        top_catalog = ranking[0][0]
        assert top_catalog == CatalogType.NED
    
    def test_agn_ranking(self):
        """Test that NED ranks high for AGN."""
        ranking = CatalogRanker.rank_for_class(ObjectClass.AGN)
        top_catalog = ranking[0][0]
        assert top_catalog == CatalogType.NED
    
    def test_nebula_ranking(self):
        """Test that SIMBAD ranks high for nebulae."""
        ranking = CatalogRanker.rank_for_class(ObjectClass.NEBULA)
        top_catalog = ranking[0][0]
        assert top_catalog == CatalogType.SIMBAD
    
    def test_cluster_ranking(self):
        """Test that Gaia or SIMBAD rank high for clusters."""
        ranking = CatalogRanker.rank_for_class(ObjectClass.CLUSTER)
        top_catalogs = [cat for cat, _ in ranking[:2]]
        assert CatalogType.GAIA in top_catalogs or CatalogType.SIMBAD in top_catalogs
    
    def test_supernova_ranking(self):
        """Test that ZTF ranks high for supernovae."""
        ranking = CatalogRanker.rank_for_class(ObjectClass.SNE)
        top_catalog = ranking[0][0]
        assert top_catalog == CatalogType.ZTF
    
    def test_ranking_scores_valid(self):
        """Test that all scores are in valid range [0, 1]."""
        for obj_class in ObjectClass:
            ranking = CatalogRanker.rank_for_class(obj_class)
            for _, score in ranking:
                assert 0.0 <= score <= 1.0, f"Invalid score for {obj_class}: {score}"
    
    def test_property_modifiers_ir(self):
        """Test that IR wavelength boosts WISE."""
        ranking_no_ir = CatalogRanker.rank_for_class(ObjectClass.STAR)
        ranking_ir = CatalogRanker.rank_for_class(ObjectClass.STAR, {"wavelength_ir": True})
        
        # Find WISE position in both
        wise_pos_no_ir = next(i for i, (cat, _) in enumerate(ranking_no_ir) if cat == CatalogType.WISE)
        wise_pos_ir = next(i for i, (cat, _) in enumerate(ranking_ir) if cat == CatalogType.WISE)
        
        # WISE should rank better with IR flag
        assert wise_pos_ir <= wise_pos_no_ir
    
    def test_property_modifiers_variability(self):
        """Test that variability boosts ZTF."""
        ranking_no_var = CatalogRanker.rank_for_class(ObjectClass.STAR)
        ranking_var = CatalogRanker.rank_for_class(ObjectClass.STAR, {"variability": True})
        
        # Find ZTF position in both
        ztf_pos_no_var = next(i for i, (cat, _) in enumerate(ranking_no_var) if cat == CatalogType.ZTF)
        ztf_pos_var = next(i for i, (cat, _) in enumerate(ranking_var) if cat == CatalogType.ZTF)
        
        # ZTF should rank better with variability flag
        assert ztf_pos_var <= ztf_pos_no_var


class TestQueryParsing:
    """Test full query parsing and routing."""
    
    def test_parse_star_query(self):
        """Test parsing a star query."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find nearby red dwarf stars")
        
        assert decision.object_class == ObjectClass.STAR
        assert len(decision.catalog_priority) > 0
        assert decision.get_top_catalogs(1)[0] == CatalogType.GAIA
        assert decision.search_radius_arcsec > 0
    
    def test_parse_galaxy_query(self):
        """Test parsing a galaxy query."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find nearby spiral galaxies")
        
        assert decision.object_class == ObjectClass.GALAXY
        assert decision.get_top_catalogs(1)[0] == CatalogType.NED
        assert decision.search_radius_arcsec > 0
    
    def test_parse_with_properties(self):
        """Test query with multiple properties."""
        router = NLPQueryRouter()
        decision = router.parse_query(
            "Find variable high-redshift quasars in the infrared"
        )
        
        assert decision.object_class == ObjectClass.QUASAR
        assert decision.search_radius_arcsec > 0
        # Should boost WISE for infrared
        wise_score = decision.get_catalog_score(CatalogType.WISE)
        assert wise_score is not None
    
    def test_routing_decision_get_top_catalogs(self):
        """Test RoutingDecision.get_top_catalogs()."""
        catalogs = [
            (CatalogType.GAIA, 0.95),
            (CatalogType.SIMBAD, 0.90),
            (CatalogType.NED, 0.70),
            (CatalogType.SDSS, 0.60)
        ]
        decision = RoutingDecision(catalogs, ObjectClass.STAR, 60, "test")
        
        top3 = decision.get_top_catalogs(3)
        assert len(top3) == 3
        assert top3 == [CatalogType.GAIA, CatalogType.SIMBAD, CatalogType.NED]
    
    def test_routing_decision_get_catalog_score(self):
        """Test RoutingDecision.get_catalog_score()."""
        catalogs = [
            (CatalogType.GAIA, 0.95),
            (CatalogType.SIMBAD, 0.90),
            (CatalogType.NED, 0.70)
        ]
        decision = RoutingDecision(catalogs, ObjectClass.STAR, 60, "test")
        
        gaia_score = decision.get_catalog_score(CatalogType.GAIA)
        assert gaia_score == 0.95
        
        missing_score = decision.get_catalog_score(CatalogType.WISE)
        assert missing_score is None


class TestSearchRadiusEstimation:
    """Test search radius estimation."""
    
    def test_explicit_arcsec_radius(self):
        """Test extracting explicit arcsecond radius."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find stars within 30 arcsec")
        assert decision.search_radius_arcsec == 30
    
    def test_explicit_arcmin_radius(self):
        """Test extracting explicit arcminute radius."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find galaxies within 2 arcmin")
        assert decision.search_radius_arcsec == 120  # 2 arcmin = 120 arcsec
    
    def test_default_star_radius(self):
        """Test default radius for stars."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find a red dwarf star")
        # Default for star is 10 arcsec
        assert decision.search_radius_arcsec == 10
    
    def test_default_nebula_radius(self):
        """Test default radius for nebulae."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find a planetary nebula")
        # Default for nebula is 120 arcsec
        assert decision.search_radius_arcsec == 120
    
    def test_default_cluster_radius(self):
        """Test default radius for clusters."""
        router = NLPQueryRouter()
        decision = router.parse_query("Find a star cluster")
        # Default for cluster is 300 arcsec
        assert decision.search_radius_arcsec == 300


class TestPropertyExtraction:
    """Test query property extraction."""
    
    def test_extract_infrared_property(self):
        """Test IR property detection."""
        router = NLPQueryRouter()
        props = router._extract_properties("Find infrared sources")
        assert props.get("wavelength_ir") is True
    
    def test_extract_variability_property(self):
        """Test variability property detection."""
        router = NLPQueryRouter()
        props = router._extract_properties("Find variable stars")
        assert props.get("variability") is True
    
    def test_extract_distance_property(self):
        """Test distance property detection."""
        router = NLPQueryRouter()
        props = router._extract_properties("Find nearby objects")
        assert props.get("nearby") is True
    
    def test_extract_redshift_property(self):
        """Test redshift property detection."""
        router = NLPQueryRouter()
        props = router._extract_properties("Find high-redshift galaxies")
        assert props.get("high_redshift") is True
    
    def test_extract_brightness_properties(self):
        """Test brightness property detection."""
        router = NLPQueryRouter()
        
        bright_props = router._extract_properties("Find bright stars with mag < 10")
        assert bright_props.get("bright") is True
        
        faint_props = router._extract_properties("Find faint objects with mag > 20")
        assert faint_props.get("faint") is True
