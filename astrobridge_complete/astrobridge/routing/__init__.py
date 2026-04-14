"""Query routing package.

Exports the public routing interface so callers can write:

    from astrobridge.routing import NLPQueryRouter, CatalogRanker
    from astrobridge.routing.base import CatalogType, ObjectClass, RoutingDecision
"""
from astrobridge.routing.base import CatalogType, ObjectClass, RoutingDecision
from astrobridge.routing.intelligent import CatalogRanker, NLPQueryRouter

__all__ = [
    "NLPQueryRouter",
    "CatalogRanker",
    "CatalogType",
    "ObjectClass",
    "RoutingDecision",
]
