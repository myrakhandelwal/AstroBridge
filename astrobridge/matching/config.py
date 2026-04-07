"""Matching configuration and scoring parameters."""
from typing import Dict, Any
from enum import Enum


class ObjectType(str, Enum):
    """Astronomical object types for matcher configuration."""
    STAR = "star"
    GALAXY = "galaxy"
    QUASAR = "quasar"
    NEBULA = "nebula"
    UNKNOWN = "unknown"


class MatcherConfig:
    """Configuration for probabilistic matcher by object type."""
    
    # Default parameters for each object type
    DEFAULTS = {
        ObjectType.STAR: {
            "positional_sigma_threshold": 2.5,
            "confidence_threshold": 0.7,
            "prior_match_prob": 0.15,
            "search_radius_arcsec": 15.0,
            "photometry_tolerance": 0.3
        },
        ObjectType.GALAXY: {
            "positional_sigma_threshold": 3.0,
            "confidence_threshold": 0.6,
            "prior_match_prob": 0.10,
            "search_radius_arcsec": 20.0,
            "photometry_tolerance": 0.5
        },
        ObjectType.QUASAR: {
            "positional_sigma_threshold": 2.0,
            "confidence_threshold": 0.75,
            "prior_match_prob": 0.05,
            "search_radius_arcsec": 10.0,
            "photometry_tolerance": 0.4
        },
        ObjectType.UNKNOWN: {
            "positional_sigma_threshold": 3.0,
            "confidence_threshold": 0.5,
            "prior_match_prob": 0.10,
            "search_radius_arcsec": 30.0,
            "photometry_tolerance": 0.5
        }
    }
    
    def __init__(self, object_type: ObjectType = ObjectType.UNKNOWN):
        """Initialize config for object type."""
        self.object_type = object_type
        self.params = self.DEFAULTS[object_type].copy()
    
    def get_param(self, name: str) -> Any:
        """Get configuration parameter."""
        return self.params.get(name)
    
    def set_param(self, name: str, value: Any) -> None:
        """Set configuration parameter."""
        self.params[name] = value
    
    def get_all_params(self) -> Dict[str, Any]:
        """Get all parameters."""
        return self.params.copy()
