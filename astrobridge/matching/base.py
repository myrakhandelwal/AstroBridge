"""Base matcher classes and exceptions."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class MatcherError(Exception):
    """Exception raised for matcher-related errors."""
    pass


class Matcher(ABC):
    """Abstract base class for astronomical source matchers."""
    
    @abstractmethod
    def match(self, sources1: List[Any], sources2: List[Any]) -> Dict[str, Any]:
        """
        Match sources from two lists.
        
        Args:
            sources1: First list of sources
            sources2: Second list of sources
            
        Returns:
            Dictionary containing match results
        """
        pass
