"""Intelligent query routing with NLP and catalog ranking."""
import logging
import re
from typing import Any, Optional

from .base import CatalogType, ObjectClass, QueryRouter, RoutingDecision

logger = logging.getLogger(__name__)


class CatalogRanker:
    """Ranks catalogs based on object type and query properties."""
    
    # Catalog strengths by object type
    CATALOG_STRENGTHS = {
        ObjectClass.STAR: {
            CatalogType.GAIA: 0.95,              # Astrometry champion + proper motions
            CatalogType.SIMBAD: 0.90,            # Comprehensive stellar data
            CatalogType.HIPPARCOS: 0.85,         # Bright-star reference (V < 12)
            CatalogType.TWOMASS: 0.80,           # NIR magnitudes for all stars
            CatalogType.SDSS: 0.75,              # Good optical photometry
            CatalogType.PANSTARRS: 0.70,         # Multi-epoch imaging
            CatalogType.ZTF: 0.60,               # Variable stars
            CatalogType.NED: 0.20,               # Not designed for stars
            CatalogType.WISE: 0.50,              # Mid-IR photometry
            CatalogType.ALLWISE: 0.55,           # AllWISE improves WISE for stars
            CatalogType.ATLAS: 0.45,             # Alert stream for variables
            CatalogType.VIZIER: 0.65,            # VizieR hosts many stellar catalogs
            CatalogType.EXOPLANET_ARCHIVE: 0.30, # Stellar hosts only
        },
        ObjectClass.GALAXY: {
            CatalogType.NED: 0.95,               # Galaxy database
            CatalogType.SDSS: 0.85,              # Large photometric survey
            CatalogType.WISE: 0.75,              # Infrared selected
            CatalogType.ALLWISE: 0.78,           # Better coverage than WISE alone
            CatalogType.SIMBAD: 0.70,            # Bright galaxies
            CatalogType.PANSTARRS: 0.60,         # Optical photometry
            CatalogType.GAIA: 0.30,              # Not primary focus
            CatalogType.ZTF: 0.40,               # Variable galaxies/AGN
            CatalogType.TWOMASS: 0.60,           # NIR for nearby galaxies
            CatalogType.VIZIER: 0.65,            # RC3, HyperLEDA etc.
            CatalogType.HIPPARCOS: 0.05,         # Irrelevant
            CatalogType.ATLAS: 0.30,
            CatalogType.EXOPLANET_ARCHIVE: 0.05,
        },
        ObjectClass.QUASAR: {
            CatalogType.NED: 0.90,               # Quasar catalog
            CatalogType.SDSS: 0.85,              # SDSS quasar survey
            CatalogType.WISE: 0.80,              # Infrared-selected QSOs
            CatalogType.ALLWISE: 0.82,           # Better for high-z QSOs
            CatalogType.ZTF: 0.70,               # Variable QSOs
            CatalogType.PANSTARRS: 0.65,         # Multi-color QSOs
            CatalogType.SIMBAD: 0.60,            # Bright QSOs
            CatalogType.GAIA: 0.30,              # Most too faint
            CatalogType.VIZIER: 0.70,            # SDSS QSO catalogs on VizieR
            CatalogType.TWOMASS: 0.35,
            CatalogType.HIPPARCOS: 0.05,
            CatalogType.ATLAS: 0.40,
            CatalogType.EXOPLANET_ARCHIVE: 0.05,
        },
        ObjectClass.AGN: {
            CatalogType.NED: 0.92,               # AGN catalog
            CatalogType.WISE: 0.88,              # Infrared AGN selection
            CatalogType.ALLWISE: 0.90,           # AllWISE AGN colors
            CatalogType.SDSS: 0.80,              # AGN spectroscopic survey
            CatalogType.ZTF: 0.75,               # Variable AGN
            CatalogType.PANSTARRS: 0.65,         # Optical AGN
            CatalogType.SIMBAD: 0.55,            # AGN subset
            CatalogType.GAIA: 0.25,              # Most AGN too faint
            CatalogType.VIZIER: 0.60,
            CatalogType.TWOMASS: 0.40,
            CatalogType.HIPPARCOS: 0.05,
            CatalogType.ATLAS: 0.45,
            CatalogType.EXOPLANET_ARCHIVE: 0.05,
        },
        ObjectClass.NEBULA: {
            CatalogType.SIMBAD: 0.90,            # Emission nebulae
            CatalogType.PANSTARRS: 0.75,         # Nearby nebulae
            CatalogType.WISE: 0.70,              # Infrared nebulae
            CatalogType.ALLWISE: 0.72,
            CatalogType.SDSS: 0.60,              # In survey areas
            CatalogType.GAIA: 0.50,              # Background stars / dust
            CatalogType.NED: 0.40,               # HII regions
            CatalogType.ZTF: 0.30,               # Transient detection
            CatalogType.TWOMASS: 0.55,           # Infrared nebulae
            CatalogType.VIZIER: 0.60,
            CatalogType.HIPPARCOS: 0.10,
            CatalogType.ATLAS: 0.20,
            CatalogType.EXOPLANET_ARCHIVE: 0.05,
        },
        ObjectClass.CLUSTER: {
            CatalogType.GAIA: 0.95,              # Best for cluster membership
            CatalogType.SIMBAD: 0.85,            # Cluster database
            CatalogType.HIPPARCOS: 0.75,         # Bright open clusters
            CatalogType.PANSTARRS: 0.75,         # Cluster member photometry
            CatalogType.SDSS: 0.70,              # Globular clusters in footprint
            CatalogType.TWOMASS: 0.70,           # NIR cluster studies
            CatalogType.WISE: 0.50,              # Infrared clusters
            CatalogType.ALLWISE: 0.52,
            CatalogType.NED: 0.40,               # Galaxy clusters
            CatalogType.ZTF: 0.30,
            CatalogType.VIZIER: 0.65,
            CatalogType.ATLAS: 0.25,
            CatalogType.EXOPLANET_ARCHIVE: 0.05,
        },
        ObjectClass.SNE: {
            CatalogType.ZTF: 0.95,               # Active SN monitoring
            CatalogType.PANSTARRS: 0.85,         # SN discovery survey
            CatalogType.ATLAS: 0.80,             # ATLAS SN alerts
            CatalogType.SDSS: 0.70,              # Historical SNe
            CatalogType.WISE: 0.50,              # Infrared SNe
            CatalogType.ALLWISE: 0.50,
            CatalogType.SIMBAD: 0.60,            # SN locations
            CatalogType.NED: 0.55,               # Host galaxies
            CatalogType.GAIA: 0.30,
            CatalogType.TWOMASS: 0.35,
            CatalogType.VIZIER: 0.50,
            CatalogType.HIPPARCOS: 0.05,
            CatalogType.EXOPLANET_ARCHIVE: 0.05,
        },
        ObjectClass.UNKNOWN: {
            CatalogType.SIMBAD: 0.80,            # Most comprehensive
            CatalogType.NED: 0.70,               # Extragalactic objects
            CatalogType.GAIA: 0.75,              # Accurate positions
            CatalogType.SDSS: 0.65,              # Large photometric survey
            CatalogType.PANSTARRS: 0.60,         # Multi-epoch
            CatalogType.WISE: 0.50,              # Infrared fallback
            CatalogType.ALLWISE: 0.52,
            CatalogType.ZTF: 0.40,               # Transient detection
            CatalogType.TWOMASS: 0.55,           # NIR fallback
            CatalogType.VIZIER: 0.60,
            CatalogType.HIPPARCOS: 0.30,
            CatalogType.ATLAS: 0.35,
            CatalogType.EXOPLANET_ARCHIVE: 0.20,
        },
    }

    # Strength modifiers by query properties
    PROPERTY_MODIFIERS = {
        "wavelength_ir": {
            CatalogType.WISE: 0.15, CatalogType.ALLWISE: 0.15,
            CatalogType.TWOMASS: 0.10, CatalogType.SDSS: -0.10,
        },
        "wavelength_uv": {CatalogType.PANSTARRS: 0.10, CatalogType.SDSS: 0.10},
        "wavelength_radio": {CatalogType.NED: 0.15, CatalogType.VIZIER: 0.10},
        "variability": {
            CatalogType.ZTF: 0.20, CatalogType.PANSTARRS: 0.10,
            CatalogType.ATLAS: 0.15,
        },
        "high_redshift": {CatalogType.NED: 0.15, CatalogType.SDSS: 0.10},
        "nearby": {
            CatalogType.GAIA: 0.15, CatalogType.HIPPARCOS: 0.15,
            CatalogType.PANSTARRS: 0.10, CatalogType.TWOMASS: 0.05,
        },
        "faint": {CatalogType.SDSS: 0.05, CatalogType.WISE: 0.10},
        "bright": {
            CatalogType.GAIA: 0.10, CatalogType.SIMBAD: 0.10,
            CatalogType.HIPPARCOS: 0.15,
        },
        "exoplanet": {CatalogType.EXOPLANET_ARCHIVE: 0.40, CatalogType.GAIA: 0.10},
        "nir": {CatalogType.TWOMASS: 0.20, CatalogType.ALLWISE: 0.10},
    }
    
    @staticmethod
    def rank_for_class(
        object_class: ObjectClass,
        query_properties: Optional[dict[str, Any]] = None
    ) -> list[tuple[CatalogType, float]]:
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
    
    def __init__(self) -> None:
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
    
    # Negation patterns that flip a keyword match to UNKNOWN
    _NEGATION_RE = re.compile(
        r"\b(?:not\s+(?:a\s+)?|non[- ]?|exclude\s+|excluding\s+|without\s+|isn'?t\s+(?:a\s+)?|no\s+)",
        re.IGNORECASE,
    )

    def classify_object(self, query: str) -> ObjectClass:
        """
        Classify object type from query string.

        Handles negation patterns such as "not a star" or "non-stellar"
        by checking whether the matched keyword sits inside a negation
        phrase. If every match for a class is negated, that class is
        skipped.

        Args:
            query: Query string

        Returns:
            ObjectClass classification
        """
        query_lower = query.lower()

        keyword_groups: list[tuple[ObjectClass, list[str]]] = [
            (ObjectClass.SNE, self.SNE_KEYWORDS),
            (ObjectClass.QUASAR, self.QUASAR_KEYWORDS),
            (ObjectClass.AGN, self.AGN_KEYWORDS),
            (ObjectClass.GALAXY, self.GALAXY_KEYWORDS),
            (ObjectClass.CLUSTER, self.CLUSTER_KEYWORDS),
            (ObjectClass.NEBULA, self.NEBULA_KEYWORDS),
            (ObjectClass.STAR, self.STAR_KEYWORDS),
        ]

        for obj_class, keywords in keyword_groups:
            if self._has_unnegated_match(query_lower, keywords):
                return obj_class

        return ObjectClass.UNKNOWN

    def _has_unnegated_match(self, query_lower: str, keywords: list[str]) -> bool:
        """Return True if at least one keyword matches without being negated."""
        for kw in keywords:
            start = 0
            while True:
                idx = query_lower.find(kw, start)
                if idx == -1:
                    break
                # Check whether a negation phrase immediately precedes the keyword
                prefix = query_lower[:idx]
                match = self._NEGATION_RE.search(prefix)
                if match and match.end() == idx:
                    # This keyword occurrence is negated — try next occurrence
                    start = idx + len(kw)
                    continue
                return True
        return False
    
    def rank_catalogs(
        self,
        object_class: ObjectClass,
        query_properties: dict[str, Any]
    ) -> list[tuple[CatalogType, float]]:
        """
        Rank catalogs by relevance.
        
        Args:
            object_class: Object classification
            query_properties: Query parameters
            
        Returns:
            List of (catalog, score) tuples
        """
        return self.ranker.rank_for_class(object_class, query_properties)
    
    def _extract_properties(self, query: str) -> dict[str, Any]:
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

        # Exoplanet indicators
        if any(e in query_lower for e in ["exoplanet", "planet", "transit", "hot jupiter", "tess", "kepler"]):
            props["exoplanet"] = True

        # Near-infrared indicators
        if any(n in query_lower for n in ["2mass", "j-band", "h-band", "k-band", "ks", "near-ir", "nir"]):
            props["nir"] = True

        return props
    
    def _estimate_search_radius(self, query: str, object_class: ObjectClass) -> float:
        """Estimate search radius from query context."""
        query_lower = query.lower()
        
        # Look for explicit radius
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
        query_props: dict[str, Any],
        catalog_priority: list[tuple[CatalogType, float]]
    ) -> str:
        """Build human-readable explanation of routing decision."""
        top_catalogs = [f"{cat.value}({score:.2f})" for cat, score in catalog_priority[:3]]
        props_str = ", ".join(query_props.keys()) if query_props else "none"
        
        return (
            f"Routed {object_class.value} query with properties {{{props_str}}} "
            f"to: {', '.join(top_catalogs)}"
        )
