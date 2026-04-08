"""Intelligent query routing with NLP and catalog ranking."""
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from .base import (
    QueryRouter, RouterError, RoutingDecision,
    CatalogType, ObjectClass
)

logger = logging.getLogger(__name__)


class CatalogRanker(object):
    """Ranks catalogs based on object type and query properties."""
    
    # Catalog strengths by object type
    CATALOG_STRENGTHS = {
        ObjectClass.STAR: {
            CatalogType.GAIA: 0.95,          # Astrometry champion
            CatalogType.SIMBAD: 0.90,        # Comprehensive stellar data
            CatalogType.SDSS: 0.75,          # Good photometry
            CatalogType.PANSTARRS: 0.70,     # Multi-epoch imaging
            CatalogType.ZTF: 0.60,           # Variable stars
            CatalogType.NED: 0.20,           # Not designed for stars
            CatalogType.WISE: 0.50,          # Infrared photometry
        },
        ObjectClass.GALAXY: {
            CatalogType.NED: 0.95,           # Galaxy database
            CatalogType.SDSS: 0.85,          # Large photometric survey
            CatalogType.SIMBAD: 0.70,        # Bright galaxies
            CatalogType.WISE: 0.75,          # Infrared selected
            CatalogType.PANSTARRS: 0.60,     # Optical photometry
            CatalogType.GAIA: 0.30,          # Not focus of Gaia
            CatalogType.ZTF: 0.40,           # Variable galaxies/AGN
        },
        ObjectClass.QUASAR: {
            CatalogType.NED: 0.90,           # Quasar catalog
            CatalogType.SDSS: 0.85,          # SDSS quasars
            CatalogType.WISE: 0.80,          # Infrared-selected QSOs
            CatalogType.ZTF: 0.70,           # Variable QSOs
            CatalogType.PANSTARRS: 0.65,     # Multi-color QSOs
            CatalogType.SIMBAD: 0.60,        # Bright QSOs
            CatalogType.GAIA: 0.30,          # Most too faint
        },
        ObjectClass.AGN: {
            CatalogType.NED: 0.92,           # AGN catalog
            CatalogType.WISE: 0.88,          # Infrared AGN
            CatalogType.SDSS: 0.80,          # AGN survey
            CatalogType.ZTF: 0.75,           # Variable AGN
            CatalogType.PANSTARRS: 0.65,     # Optical AGN
            CatalogType.SIMBAD: 0.55,        # AGN subset
            CatalogType.GAIA: 0.25,          # Most too faint
        },
        ObjectClass.NEBULA: {
            CatalogType.SIMBAD: 0.90,        # Emission nebulae
            CatalogType.PANSTARRS: 0.75,     # Nearby nebulae
            CatalogType.WISE: 0.70,          # Infrared nebulae
            CatalogType.SDSS: 0.60,          # In survey areas
            CatalogType.GAIA: 0.50,          # Dust extinction
            CatalogType.NED: 0.40,           # HII regions
            CatalogType.ZTF: 0.30,           # Transient detection
        },
        ObjectClass.CLUSTER: {
            CatalogType.GAIA: 0.85,          # Stellar kinematics
            CatalogType.SIMBAD: 0.85,        # Cluster database
            CatalogType.PANSTARRS: 0.75,     # Cluster members
            CatalogType.SDSS: 0.70,          # Globular clusters
            CatalogType.WISE: 0.50,          # Infrared clusters
            CatalogType.NED: 0.40,           # Galaxy clusters
            CatalogType.ZTF: 0.30,           # No cluster focus
        },
        ObjectClass.SNE: {
            CatalogType.ZTF: 0.95,           # Active supernova monitoring
            CatalogType.PANSTARRS: 0.85,     # SN discovery
            CatalogType.SDSS: 0.70,          # Historical SNe
            CatalogType.WISE: 0.50,          # Infrared SNe
            CatalogType.SIMBAD: 0.60,        # SN locations
            CatalogType.NED: 0.55,           # Host galaxies
            CatalogType.GAIA: 0.30,          # Astrometry
        },
        ObjectClass.UNKNOWN: {
            # When classification is uncertain, use balanced approach
            CatalogType.SIMBAD: 0.80,        # Most comprehensive
            CatalogType.NED: 0.70,           # Extragalactic objects
            CatalogType.GAIA: 0.75,          # Accurate positions
            CatalogType.SDSS: 0.65,          # Large photometric survey
            CatalogType.PANSTARRS: 0.60,     # Multi-epoch
            CatalogType.WISE: 0.50,          # Infrared fallback
            CatalogType.ZTF: 0.40,           # Transient detection
        }
    }
    
    # Strength modifiers by query properties
    PROPERTY_MODIFIERS = {
        "wavelength_ir": {CatalogType.WISE: 0.15, CatalogType.SDSS: -0.10},
        "wavelength_uv": {CatalogType.PANSTARRS: 0.10, CatalogType.SDSS: 0.10},
        "wavelength_radio": {CatalogType.NED: 0.15},
        "variability": {CatalogType.ZTF: 0.20, CatalogType.PANSTARRS: 0.10},
        "high_redshift": {CatalogType.NED: 0.15, CatalogType.SDSS: 0.10},
        "nearby": {CatalogType.GAIA: 0.15, CatalogType.PANSTARRS: 0.10},
        "faint": {CatalogType.SDSS: 0.05, CatalogType.WISE: 0.10},
        "bright": {CatalogType.GAIA: 0.10, CatalogType.SIMBAD: 0.10},
    }
    
    @staticmethod
    def rank_for_class(
        object_class: ObjectClass,
        query_properties: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[CatalogType, float]]:
        """
        Rank catalogs for given object class.
        
        Args:
            object_class: Object classification
            query_properties: Optional query properties for fine-tuning
            
        Returns:
            List of (catalog, score) tuples sorted by score
        """
        # Start with base strengths
        scores = CatalogRanker.CATALOG_STRENGTHS.get(
            object_class,
            CatalogRanker.CATALOG_STRENGTHS[ObjectClass.UNKNOWN]
        ).copy()
        
        # Apply property-based modifiers
        if query_properties:
            for prop, modifiers in CatalogRanker.PROPERTY_MODIFIERS.items():
                if prop in query_properties and query_properties[prop]:
                    for catalog, modifier in modifiers.items():
                        scores[catalog] = max(0.0, min(1.0, scores.get(catalog, 0.5) + modifier))
        
        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked


class NLPQueryRouter(QueryRouter):
    """Natural language query router with intelligent catalog selection."""
    
    # Keywords for object classification
    STAR_KEYWORDS = [
        "star", "stellar", "main sequence", "giant", "dwarf",
        "white dwarf", "neutron star", "pulsar", "binary", "eclipsing"
    ]
    
    GALAXY_KEYWORDS = [
        "galaxy", "galaxies", "gal", "spiral", "elliptical", "irregular",
        "dwarf galaxy", "lenticular", "sb", "e0", "s0", "hubble"
    ]
    
    QUASAR_KEYWORDS = [
        "quasar", "qso", "quasi-stellar", "q0", "3c", "3cr"
    ]
    
    AGN_KEYWORDS = [
        "agn", "active galactic", "active nucleus", "seyfert", "blazar",
        "bll", "bl lac", "fsrq", "core-jet"
    ]
    
    NEBULA_KEYWORDS = [
        "nebula", "nebulae", "emission", "dark cloud", "planetary nebula",
        "supernova remnant", "snr", "hii region", "pn"
    ]
    
    CLUSTER_KEYWORDS = [
        "cluster", "star cluster", "globular", "open cluster", "gc", "oc",
        "m13", "m51", "assoc"
    ]
    
    SNE_KEYWORDS = [
        "supernova", "sne", "sn ", "transient", "explosion", "transients"
    ]
    
    def __init__(self):
        """Initialize NLP router."""
        logger.info("Initialized NLPQueryRouter")
        self.ranker = CatalogRanker()
    
    def parse_query(self, query: str) -> RoutingDecision:
        """
        Parse natural language query and route to appropriate catalogs.
        
        Args:
            query: Query string (e.g., "Find nearby red dwarf stars")
            
        Returns:
            RoutingDecision with routing strategy
        """
        logger.info(f"Parsing query: {query}")
        
        # Classify object type
        object_class = self.classify_object(query)
        logger.debug(f"Classified as: {object_class}")
        
        # Extract query properties
        query_props = self._extract_properties(query)
        logger.debug(f"Query properties: {query_props}")
        
        # Estimate search radius
        radius_arcsec = self._estimate_search_radius(query, object_class)
        logger.debug(f"Estimated search radius: {radius_arcsec} arcsec")
        
        # Rank catalogs
        catalog_priority = self.rank_catalogs(object_class, query_props)
        
        # Build reasoning
        reasoning = self._build_reasoning(object_class, query_props, catalog_priority)
        
        decision = RoutingDecision(
            catalog_priority=catalog_priority,
            object_class=object_class,
            search_radius_arcsec=radius_arcsec,
            reasoning=reasoning
        )
        
        logger.info(f"Routing decision: {reasoning}")
        return decision
    
    def classify_object(self, query: str) -> ObjectClass:
        """
        Classify object type from query string.
        
        Args:
            query: Query string
            
        Returns:
            ObjectClass classification
        """
        query_lower = query.lower()
        
        # Check each classification in order
        if any(kw in query_lower for kw in self.SNE_KEYWORDS):
            return ObjectClass.SNE
        if any(kw in query_lower for kw in self.QUASAR_KEYWORDS):
            return ObjectClass.QUASAR
        if any(kw in query_lower for kw in self.AGN_KEYWORDS):
            return ObjectClass.AGN
        if any(kw in query_lower for kw in self.GALAXY_KEYWORDS):
            return ObjectClass.GALAXY
        if any(kw in query_lower for kw in self.CLUSTER_KEYWORDS):
            return ObjectClass.CLUSTER
        if any(kw in query_lower for kw in self.NEBULA_KEYWORDS):
            return ObjectClass.NEBULA
        if any(kw in query_lower for kw in self.STAR_KEYWORDS):
            return ObjectClass.STAR
        
        return ObjectClass.UNKNOWN
    
    def rank_catalogs(
        self,
        object_class: ObjectClass,
        query_properties: Dict[str, Any]
    ) -> List[Tuple[CatalogType, float]]:
        """
        Rank catalogs by relevance.
        
        Args:
            object_class: Object classification
            query_properties: Query parameters
            
        Returns:
            List of (catalog, score) tuples
        """
        return self.ranker.rank_for_class(object_class, query_properties)
    
    def _extract_properties(self, query: str) -> Dict[str, Any]:
        """Extract query properties from natural language."""
        props = {}
        query_lower = query.lower()
        
        # Wavelength detection
        if any(w in query_lower for w in ["infrared", "ir", "wise", "mid-ir"]):
            props["wavelength_ir"] = True
        if any(w in query_lower for w in ["ultraviolet", "uv", "far-uv"]):
            props["wavelength_uv"] = True
        if any(w in query_lower for w in ["radio", "radio source"]):
            props["wavelength_radio"] = True
        
        # Variability
        if any(v in query_lower for v in ["variable", "transient", "flare", "burst"]):
            props["variability"] = True
        
        # Redshift indicators
        if any(z in query_lower for z in ["high-z", "high redshift", "high-redshift", "distant", "early universe"]):
            props["high_redshift"] = True
        
        # Distance indicators
        if any(d in query_lower for d in ["nearby", "close", "local", "within 100 pc"]):
            props["nearby"] = True
        
        # Magnitude indicators
        if any(f in query_lower for f in ["bright", "mag < 10", "magnitude <", "v < 10"]):
            props["bright"] = True
        if any(f in query_lower for f in ["faint", "mag > 20", "magnitude >", "v > 20"]):
            props["faint"] = True
        
        return props
    
    def _estimate_search_radius(self, query: str, object_class: ObjectClass) -> float:
        """Estimate search radius from query context."""
        query_lower = query.lower()
        
        # Look for explicit radius
        import re
        radius_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:arcmin|arcminute|")', query_lower)
        if radius_match:
            arcmin = float(radius_match.group(1))
            return arcmin * 60  # Convert to arcsec
        
        radius_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:arcsec|arcsecond)', query_lower)
        if radius_match:
            return float(radius_match.group(1))
        
        # Default radii by object class
        defaults = {
            ObjectClass.STAR: 10,         # Stars are point sources
            ObjectClass.GALAXY: 30,       # Galaxies vary in size
            ObjectClass.QUASAR: 10,       # Quasars are point sources
            ObjectClass.AGN: 20,          # AGN cores
            ObjectClass.NEBULA: 120,      # Nebulae can be large
            ObjectClass.CLUSTER: 300,     # Clusters span degrees
            ObjectClass.SNE: 60,          # Supernovae searching region
            ObjectClass.UNKNOWN: 60,      # Conservative default
        }
        
        return defaults.get(object_class, 60)
    
    def _build_reasoning(
        self,
        object_class: ObjectClass,
        query_props: Dict[str, Any],
        catalog_priority: List[Tuple[CatalogType, float]]
    ) -> str:
        """Build human-readable explanation of routing decision."""
        top_catalogs = [f"{cat.value}({score:.2f})" for cat, score in catalog_priority[:3]]
        props_str = ", ".join(query_props.keys()) if query_props else "none"
        
        return (
            f"Routed {object_class.value} query with properties {{{props_str}}} "
            f"to: {', '.join(top_catalogs)}"
        )
