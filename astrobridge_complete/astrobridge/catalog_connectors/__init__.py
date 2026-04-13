"""Abstract base class that every catalog connector must implement.

Design note: the interface is intentionally minimal.  Connectors own their
own retry/timeout logic; callers only see clean results or exceptions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from astrobridge.models import Source


class CatalogConnector(ABC):
    """Base class for all astronomical catalog adapters."""

    # ------------------------------------------------------------------
    # Required interface
    # ------------------------------------------------------------------

    @abstractmethod
    def query_by_name(self, name: str) -> Optional[Source]:
        """Return the best-matching Source for *name*, or None."""
        raise NotImplementedError

    @abstractmethod
    async def query_object(self, name: str) -> List[Source]:
        """Async name-based lookup returning all matching sources."""
        raise NotImplementedError

    @abstractmethod
    async def cone_search(
        self, ra: float, dec: float, radius_arcsec: float
    ) -> List[Source]:
        """Return all sources within *radius_arcsec* of (ra, dec)."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_name(name: str) -> str:
        """Strip spaces and lower-case for fuzzy matching."""
        return "".join(ch.lower() for ch in name if ch.isalnum())

    @staticmethod
    def _escape_adql(value: str) -> str:
        """Escape a string literal for safe ADQL embedding."""
        dangerous = ["--", "/*", "*/", ";", "\x00"]
        lower = value.lower()
        for pat in dangerous:
            if pat in lower:
                raise ValueError(
                    f"String contains unsafe ADQL pattern: {pat!r}"
                )
        return value.replace("'", "''")
