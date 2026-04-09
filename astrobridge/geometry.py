"""Shared geometry helpers for astronomical coordinates."""
import numpy as np


def angular_distance_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Compute angular separation in degrees using the Haversine formula.
    
    This formula provides accurate results across all angular separations,
    from arcseconds to full-sky distances, unlike the small-angle approximation.
    
    Uses the haversine formula:
        a = sin²(Δ𝛿/2) + cos(𝛿₁)*cos(𝛿₂)*sin²(Δ𝛼/2)
        c = 2*atan2(√a, √(1-a))
    
    Args:
        ra1: Right ascension of first source in degrees
        dec1: Declination of first source in degrees
        ra2: Right ascension of second source in degrees
        dec2: Declination of second source in degrees
        
    Returns:
        Angular separation in degrees
        
    Notes:
        Haversine is numerically stable for small angles (< 1 arcsecond)
        and accurate for large angles (> 10 degrees) where Euclidean fails.
    """
    # Convert to radians
    ra1_rad = np.radians(ra1)
    dec1_rad = np.radians(dec1)
    ra2_rad = np.radians(ra2)
    dec2_rad = np.radians(dec2)
    
    # Haversine formula
    dra = ra2_rad - ra1_rad
    ddec = dec2_rad - dec1_rad
    
    a = np.sin(ddec / 2) ** 2 + np.cos(dec1_rad) * np.cos(dec2_rad) * np.sin(dra / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    # Convert back to degrees
    return float(np.degrees(c))


def angular_distance_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Compute angular separation in arcseconds using the Haversine formula."""
    return angular_distance_deg(ra1, dec1, ra2, dec2) * 3600.0
