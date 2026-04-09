"""AstroBridge - Astronomical source matching and cross-catalog identification."""

try:
    from astrobridge._version import __version__
except ImportError:
    __version__ = "0.3.0"  # fallback if _version.py not yet generated
