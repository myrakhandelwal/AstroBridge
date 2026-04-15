"""Base classes for query routing."""
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

from astrobridge.models import ObjectType

logger = logging.getLogger(__name__)


class RouterError(Exception):
    """Exception raised for routing-related errors."""
    pass


class CatalogType(str, Enum):
    """Enumeration of available catalogs."""
    # General / multi-wavelength
    SIMBAD = "simbad"          # CDS SIMBAD — comprehensive stellar/object DB
    NED = "ned"                # NASA Extragalactic Database
    VIZIER = "vizier"          # CDS VizieR — gateway to published catalog tables
    # Optical / astrometry
    GAIA = "gaia"              # ESA Gaia DR3 — best astrometry + proper motions
    HIPPARCOS = "hipparcos"    # ESA Hipparcos — bright-star reference catalog
    SDSS = "sdss"              # Sloan Digital Sky Survey
    PANSTARRS = "panstarrs"    # Pan-STARRS1 3π survey
    # Infrared
    WISE = "wise"              # WISE W1–W4 mid-IR
    ALLWISE = "allwise"        # AllWISE — improved WISE with proper motions
    TWOMASS = "twomass"        # 2MASS J/H/Ks near-IR all-sky
    # Time-domain / transients
    ZTF = "ztf"                # Zwicky Transient Facility
    ATLAS = "atlas"            # ATLAS survey
    # Exoplanets
    EXOPLANET_ARCHIVE = "exoplanet_archive"  # NASA Exoplanet Archive


# Backwards-compatible alias — all code that imports ObjectClass still works.
ObjectClass = ObjectType


class RoutingDecision:
    """Represents a routing decision for a query."""
    
    def __init__(
        self,
        catalog_priority: list[tuple[CatalogType, float]],
        object_class: ObjectClass,
        search_radius_arcsec: float,
        reasoning: str
    ):
        """
        Initialize routing decision.
        
        Args:
            catalog_priority: List of (catalog, relevance_score) tuples ordered by priority
            object_class: Inferred object classification
            search_radius_arcsec: Recommended search radius in arcseconds
            reasoning: Explanation of routing decision
        """
        self.catalog_priority = catalog_priority
        self.object_class = object_class
        self.search_radius_arcsec = search_radius_arcsec
        self.reasoning = reasoning
    
    def get_top_catalogs(self, n: int = 3) -> list[CatalogType]:
        """Get top n catalogs by priority."""
        return [cat for cat, _ in self.catalog_priority[:n]]
    
    def get_catalog_score(self, catalog: CatalogType) -> Optional[float]:
        """Get relevance score for a catalog."""
        for cat, score in self.catalog_priority:
            if cat == catalog:
                return score
        return None


class QueryRouter(ABC):
    """Abstract base class for query routers."""
    
    @abstractmethod
    def parse_query(self, query: str) -> RoutingDecision:
        """
        Parse a query and decide which catalogs to use.
        
        Args:
            query: Natural language query string
            
        Returns:
            RoutingDecision with catalog priorities and reasoning
        """
        pass
    
    @abstractmethod
    def classify_object(self, query: str) -> ObjectClass:
        """
        Classify the object type from a query.
        
        Args:
            query: Query string
            
        Returns:
            ObjectClass classification
        """
        pass
    
    @abstractmethod
    def rank_catalogs(
        self,
        object_class: ObjectClass,
        query_properties: dict[str, Any]
    ) -> list[tuple[CatalogType, float]]:
        """
        Rank catalogs by relevance for given object class and properties.
        
        Args:
            object_class: Classification of the target object
            query_properties: Dict with query parameters (wavelength, magnitude, etc.)
            
        Returns:
            List of (catalog, score) tuples ordered by priority
        """
        pass
