"""Base types and abstract interface for query routing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CatalogType(str, Enum):
    """Supported astronomical catalogs."""
    SIMBAD = "SIMBAD"
    NED = "NED"
    GAIA = "Gaia"
    SDSS = "SDSS"
    PANSTARRS = "Pan-STARRS"
    ZTF = "ZTF"
    WISE = "WISE"


class ObjectClass(str, Enum):
    """Astronomical object classification."""
    STAR = "star"
    GALAXY = "galaxy"
    QUASAR = "quasar"
    AGN = "agn"
    NEBULA = "nebula"
    CLUSTER = "cluster"
    SNE = "supernova"
    UNKNOWN = "unknown"


class RoutingDecision(BaseModel):
    """Output of a routing decision – which catalogs to query and why."""
    catalog_priority: list[tuple[CatalogType, float]] = Field(
        description="Ordered (catalog, score) pairs, highest first"
    )
    object_class: ObjectClass = Field(
        description="Inferred object class"
    )
    search_radius_arcsec: float = Field(
        description="Recommended cone-search radius in arcseconds"
    )
    reasoning: str = Field(
        description="Human-readable explanation of the routing decision"
    )

    def get_top_catalogs(self, n: int = 3) -> list[CatalogType]:
        """Return the top-n CatalogType values by priority score."""
        return [ct for ct, _ in self.catalog_priority[:n]]


class QueryRouter(ABC):
    """Abstract base for all query routers."""

    @abstractmethod
    def parse_query(self, query: str) -> RoutingDecision:
        """Parse a natural-language query and return a routing decision."""
        raise NotImplementedError

    @abstractmethod
    def classify_object(self, query: str) -> ObjectClass:
        """Classify the object type implied by *query*."""
        raise NotImplementedError

    @abstractmethod
    def rank_catalogs(
        self,
        object_class: ObjectClass,
        query_properties: dict[str, Any],
    ) -> list[tuple[CatalogType, float]]:
        """Return an ordered list of (catalog, score) pairs."""
        raise NotImplementedError
