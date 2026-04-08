"""External catalog connectors."""
from typing import List, Optional
from abc import ABC, abstractmethod
from .models import Coordinate, Source


class CatalogConnector(ABC):
    """Base class for catalog connectors."""
    
    @abstractmethod
    def query(self, name: str) -> Optional[Source]:
        """Query catalog for a source."""
        pass

    async def query_object(self, name: str) -> List[Source]:
        """Async-compatible object lookup used by integration paths."""
        result = self.query(name)
        return [result] if result is not None else []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> List[Source]:
        """Async-compatible cone search placeholder for future live catalog queries."""
        return []


class SimbadConnector(CatalogConnector):
    """SIMBAD catalog connector."""
    
    def query(self, name: str) -> Optional[Source]:
        """Query SIMBAD for a source."""
        return None


class NEDConnector(CatalogConnector):
    """NASA Extragalactic Database connector."""
    
    def query(self, name: str) -> Optional[Source]:
        """Query NED for a source."""
        return None
