"""Matching configuration and scoring parameters."""
from typing import Any

from astrobridge.models import ObjectType


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
        ObjectType.AGN: {
            "positional_sigma_threshold": 2.5,
            "confidence_threshold": 0.7,
            "prior_match_prob": 0.08,
            "search_radius_arcsec": 15.0,
            "photometry_tolerance": 0.4
        },
        ObjectType.NEBULA: {
            "positional_sigma_threshold": 3.5,
            "confidence_threshold": 0.5,
            "prior_match_prob": 0.10,
            "search_radius_arcsec": 60.0,
            "photometry_tolerance": 0.6
        },
        ObjectType.CLUSTER: {
            "positional_sigma_threshold": 4.0,
            "confidence_threshold": 0.5,
            "prior_match_prob": 0.10,
            "search_radius_arcsec": 120.0,
            "photometry_tolerance": 0.5
        },
        ObjectType.SNE: {
            "positional_sigma_threshold": 2.0,
            "confidence_threshold": 0.8,
            "prior_match_prob": 0.05,
            "search_radius_arcsec": 10.0,
            "photometry_tolerance": 0.3
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
    
    def get_all_params(self) -> dict[str, Any]:
        """Get all parameters."""
        return self.params.copy()
