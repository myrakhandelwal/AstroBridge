"""Astronomical source cross-matching algorithms."""
from astrobridge.matching.probabilistic import BayesianMatcher
from astrobridge.matching.base import Matcher, MatcherError
from astrobridge.matching.confidence import ConfidenceScorer, MatchScore
from astrobridge.matching.spatial import SpatialIndex

# Historical alias
ConfidenceResult = MatchScore

__all__ = [
    "BayesianMatcher", "Matcher", "MatcherError",
    "ConfidenceScorer", "ConfidenceResult", "MatchScore", "SpatialIndex",
]
