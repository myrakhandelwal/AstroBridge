"""External catalog connectors."""
from typing import List, Optional
from abc import ABC, abstractmethod
from .models import Source


class CatalogConnector(ABC):
    """Base class for catalog connectors."""
    
    @abstractmethod
    def query(self, name: str) -> Optional[Source]:
        """Query catalog for a source."""
        pass


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
