"""Base classes for query routing."""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class RouterError(Exception):
    """Exception raised for routing-related errors."""
    pass


class CatalogType(str, Enum):
    """Enumeration of available catalogs."""
    SIMBAD = "simbad"
    NED = "ned"
    GAIA = "gaia"
    SDSS = "sdss"
    WISE = "wise"
    PANSTARRS = "panstarrs"
    ZTF = "ztf"
    ATLAS = "atlas"


class ObjectClass(str, Enum):
    """Classification of astronomical objects."""
    STAR = "star"
    GALAXY = "galaxy"
    QUASAR = "quasar"
    AGN = "agn"
    NEBULA = "nebula"
    CLUSTER = "cluster"
    SNE = "sne"
    UNKNOWN = "unknown"


class RoutingDecision(object):
    """Represents a routing decision for a query."""
    
    def __init__(
        self,
        catalog_priority: List[Tuple[CatalogType, float]],
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
    
    def get_top_catalogs(self, n: int = 3) -> List[CatalogType]:
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
        query_properties: Dict[str, Any]
    ) -> List[Tuple[CatalogType, float]]:
        """
        Rank catalogs by relevance for given object class and properties.
        
        Args:
            object_class: Classification of the target object
            query_properties: Dict with query parameters (wavelength, magnitude, etc.)
            
        Returns:
            List of (catalog, score) tuples ordered by priority
        """
        pass
