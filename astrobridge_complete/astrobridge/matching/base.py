"""Base matcher classes and exceptions."""
from abc import ABC, abstractmethod
from typing import Any

from astrobridge.models import MatchResult


class MatcherError(Exception):
    """Exception raised for matcher-related errors."""
    pass


class Matcher(ABC):
    """Abstract base class for astronomical source matchers."""
    
    @abstractmethod
    def match(self, sources1: list[Any], sources2: list[Any]) -> list[MatchResult]:
        """
        Match sources from two lists.
        
        Args:
            sources1: First list of sources
            sources2: Second list of sources
            
        Returns:
            List of match results
        """
        raise NotImplementedError
