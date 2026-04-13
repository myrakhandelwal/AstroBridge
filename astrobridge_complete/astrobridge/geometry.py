"""Spherical geometry utilities.

All distance calculations use the Haversine formula which is numerically
stable for both sub-arcsecond and full-sky separations.  The flat-sky
Euclidean approximation used in some earlier modules is intentionally
*not* reproduced here.
"""

from __future__ import annotations

import math


def angular_distance_deg(
    ra1: float, dec1: float, ra2: float, dec2: float
) -> float:
    """Great-circle separation in degrees (Haversine formula).

    Parameters
    ----------
    ra1, dec1 : float
        Right ascension and declination of the first point in degrees.
    ra2, dec2 : float
        Right ascension and declination of the second point in degrees.

    Returns
    -------
    float
        Angular separation in degrees, in the range [0, 180].
    """
    ra1_r = math.radians(ra1)
    dec1_r = math.radians(dec1)
    ra2_r = math.radians(ra2)
    dec2_r = math.radians(dec2)

    d_dec = dec2_r - dec1_r
    d_ra = ra2_r - ra1_r

    # Handle RA wrap-around: keep delta in (-π, π]
    if d_ra > math.pi:
        d_ra -= 2.0 * math.pi
    elif d_ra < -math.pi:
        d_ra += 2.0 * math.pi

    a = (
        math.sin(d_dec / 2.0) ** 2
        + math.cos(dec1_r) * math.cos(dec2_r) * math.sin(d_ra / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return math.degrees(c)


def angular_distance_arcsec(
    ra1: float, dec1: float, ra2: float, dec2: float
) -> float:
    """Great-circle separation in arcseconds."""
    return angular_distance_deg(ra1, dec1, ra2, dec2) * 3600.0


def position_at_epoch(
    ra: float,
    dec: float,
    pm_ra_mas_yr: float,
    pm_dec_mas_yr: float,
    delta_years: float,
) -> tuple[float, float]:
    """Apply linear proper-motion to produce coordinates at a new epoch.

    Parameters
    ----------
    ra, dec : float  Reference position in degrees.
    pm_ra_mas_yr : float  Proper motion in RA × cos(dec) in mas/yr.
    pm_dec_mas_yr : float  Proper motion in Dec in mas/yr.
    delta_years : float  Time elapsed from reference epoch (years).

    Returns
    -------
    (ra_new, dec_new) : tuple[float, float]  in degrees.
    """
    ra_new = ra + (pm_ra_mas_yr * delta_years) / (1000.0 * 3600.0)
    dec_new = dec + (pm_dec_mas_yr * delta_years) / (1000.0 * 3600.0)

    ra_new = ra_new % 360.0
    dec_new = max(-90.0, min(90.0, dec_new))
    return ra_new, dec_new
