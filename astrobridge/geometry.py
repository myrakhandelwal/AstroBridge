"""Shared geometry helpers for astronomical coordinates."""
import numpy as np


def angular_distance_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Compute angular separation in degrees using a simple small-angle approximation."""
    return float(np.sqrt((ra1 - ra2) ** 2 + (dec1 - dec2) ** 2))


def angular_distance_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Compute angular separation in arcseconds using the small-angle approximation."""
    return angular_distance_deg(ra1, dec1, ra2, dec2) * 3600.0
