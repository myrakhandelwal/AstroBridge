"""CCD image calibration pipeline.

Performs standard CCD reduction: bias subtraction, dark subtraction, and
flat-field division.  Uses ``astropy`` + ``ccdproc`` when available; falls
back to a pure-numpy implementation so the module can be imported and tested
without the astronomy stack installed.

Calibration frames are located by consulting:
1. The SQLite ``calibration_frames`` table (preferred – managed path).
2. The directory tree under ``CALIB_PATH`` env variable as a fallback.

Directory convention under ``CALIB_PATH``::

    <CALIB_PATH>/<telescope_id>/<date_obs>/<frame_type>.fits
    e.g.  /calib/keck/2026-04-07/bias.fits

Environment variables
---------------------
CALIB_PATH : str   Root directory for calibration frames.
OUTPUT_DIR : str   Where to write calibrated FITS files (default: output/calibrated).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import warnings
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Availability guards for optional astronomy stack
# ---------------------------------------------------------------------------

def _has_astropy() -> bool:
    try:
        import astropy  # noqa: F401
        return True
    except ImportError:
        return False


def _has_ccdproc() -> bool:
    try:
        import ccdproc  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Frame path resolution
# ---------------------------------------------------------------------------

def _resolve_frame_path(
    conn: Optional[sqlite3.Connection],
    telescope_id: str,
    frame_type: str,
    date_obs: str,
) -> Optional[str]:
    """Find a calibration frame path via DB first, then filesystem fallback."""
    # 1. Database lookup
    if conn is not None:
        from astrobridge.database import get_calibration_frame
        db_path = get_calibration_frame(conn, telescope_id, frame_type, date_obs)
        if db_path and Path(db_path).exists():
            return db_path

    # 2. Filesystem fallback using CALIB_PATH convention
    calib_root = os.getenv("CALIB_PATH", "")
    if calib_root:
        candidate = Path(calib_root) / telescope_id / date_obs / f"{frame_type}.fits"
        if candidate.exists():
            return str(candidate)

        # Also try without date subdirectory (simpler convention)
        candidate2 = Path(calib_root) / telescope_id / f"{frame_type}.fits"
        if candidate2.exists():
            return str(candidate2)

    return None


# ---------------------------------------------------------------------------
# numpy-only calibration (no astropy/ccdproc dependency)
# ---------------------------------------------------------------------------

def _calibrate_numpy(
    raw_path: str,
    bias_path: Optional[str],
    dark_path: Optional[str],
    flat_path: Optional[str],
    output_path: str,
) -> str:
    """Pure numpy fallback calibration for environments without astropy.

    Reads FITS files as raw binary (minimal header parsing) and performs
    arithmetic in float64.  Writes the result as a simple FITS-like binary.

    Note: This is a development/testing fallback.  Production use should
    have astropy + ccdproc installed.
    """
    import numpy as np

    warnings.warn(
        "astropy/ccdproc not available; using numpy-only calibration fallback. "
        "Results may differ from full astropy pipeline.",
        UserWarning,
        stacklevel=3,
    )

    def _read_fits_data(path: str) -> np.ndarray:
        """Minimal FITS reader: skip 2880-byte header blocks, read image."""
        with open(path, "rb") as fh:
            raw = fh.read()
        # Find END keyword to locate start of data
        header_end = raw.find(b"END" + b" " * 77)
        if header_end == -1:
            raise ValueError(f"Could not parse FITS header in {path}")
        # Data starts at next 2880-byte boundary after header END
        hdr_bytes = header_end + 80
        data_start = ((hdr_bytes + 2879) // 2880) * 2880
        data_raw = raw[data_start:]
        # Assume 16-bit int (most common raw CCD format)
        arr = np.frombuffer(data_raw, dtype=">i2").astype(np.float64)
        # Attempt to reshape from NAXIS keywords (simplified: try square root)
        side = int(len(arr) ** 0.5)
        if side * side == len(arr):
            return arr.reshape(side, side)
        return arr

    raw_data = _read_fits_data(raw_path)
    result = raw_data.astype(np.float64)

    if bias_path:
        bias_data = _read_fits_data(bias_path).astype(np.float64)
        result -= bias_data

    if dark_path:
        dark_data = _read_fits_data(dark_path).astype(np.float64)
        result -= dark_data

    if flat_path:
        flat_data = _read_fits_data(flat_path).astype(np.float64)
        flat_norm = flat_data / np.median(flat_data[flat_data > 0])
        with np.errstate(divide="ignore", invalid="ignore"):
            result = np.where(flat_norm > 0.01, result / flat_norm, 0.0)

    # Write minimal output (numpy .npy format as stand-in)
    output_npy = output_path.replace(".fits", "_calibrated.npy")
    Path(output_npy).parent.mkdir(parents=True, exist_ok=True)
    np.save(output_npy, result)
    logger.info("Numpy calibration written to %s", output_npy)
    return output_npy


# ---------------------------------------------------------------------------
# astropy + ccdproc calibration
# ---------------------------------------------------------------------------

def _calibrate_astropy(
    raw_path: str,
    bias_path: Optional[str],
    dark_path: Optional[str],
    flat_path: Optional[str],
    output_path: str,
) -> str:
    """Full CCD calibration using astropy.nddata.CCDData and ccdproc."""
    import astropy.units as u  # type: ignore[import-untyped]
    import ccdproc as ccdp  # type: ignore[import-untyped]
    from astropy.nddata import CCDData  # type: ignore[import-untyped]

    raw_ccd: CCDData = CCDData.read(raw_path, unit=u.adu)

    # --- Bias subtraction ---
    if bias_path:
        master_bias = CCDData.read(bias_path, unit=u.adu)
        raw_ccd = ccdp.subtract_bias(raw_ccd, master_bias)
        logger.debug("Bias subtracted using %s", bias_path)

    # --- Dark subtraction ---
    if dark_path:
        master_dark = CCDData.read(dark_path, unit=u.adu)
        # Exposure times in headers are used for scaling if present
        raw_ccd = ccdp.subtract_dark(
            raw_ccd,
            master_dark,
            exposure_time="exptime",
            exposure_unit=u.second,
            scale=True,
        )
        logger.debug("Dark subtracted using %s", dark_path)

    # --- Flat-field division ---
    if flat_path:
        master_flat = CCDData.read(flat_path, unit=u.adu)
        raw_ccd = ccdp.flat_correct(raw_ccd, master_flat)
        logger.debug("Flat corrected using %s", flat_path)

    # --- Write output ---
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    raw_ccd.write(output_path, overwrite=True)
    logger.info("Calibrated FITS written to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calibrate_ccd(
    raw_fits_path: str,
    telescope_id: str,
    date_obs: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Calibrate a raw CCD FITS image.

    Applies bias subtraction, dark subtraction, and flat-field division using
    master calibration frames found via the database or ``CALIB_PATH``.

    Parameters
    ----------
    raw_fits_path :
        Path to the raw (uncalibrated) FITS file.
    telescope_id :
        Telescope identifier used to look up matching calibration frames
        (e.g. ``"keck-lris"``, ``"vlt-fors2"``).
    date_obs :
        Observation date string (``YYYY-MM-DD``).  If None, today's date is
        used.  Used to look up the correct night's calibration frames.
    conn :
        Open SQLite connection for calibration-frame lookup.  Pass None to
        use filesystem-only lookup.
    output_dir :
        Directory where the calibrated file is written.  Defaults to the
        ``OUTPUT_DIR`` environment variable or ``output/calibrated``.

    Returns
    -------
    str
        Path to the calibrated output file.  Returns ``raw_fits_path`` unchanged
        if no calibration frames are found (with a logged warning).
    """
    raw_path = Path(raw_fits_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"Raw FITS file not found: {raw_fits_path}")

    # Resolve observation date
    if date_obs is None:
        from datetime import date
        date_obs = date.today().isoformat()

    # Resolve output path
    out_base = output_dir or os.getenv("OUTPUT_DIR", "output/calibrated")
    output_path = str(
        Path(out_base) / f"{telescope_id}_{date_obs}_{raw_path.stem}_cal.fits"
    )

    # Resolve calibration frames
    bias_path = _resolve_frame_path(conn, telescope_id, "bias", date_obs)
    dark_path = _resolve_frame_path(conn, telescope_id, "dark", date_obs)
    flat_path = _resolve_frame_path(conn, telescope_id, "flat", date_obs)

    if not any([bias_path, dark_path, flat_path]):
        logger.warning(
            "No calibration frames found for telescope '%s' on %s. "
            "Returning raw file path unchanged.",
            telescope_id,
            date_obs,
        )
        return raw_fits_path

    # Dispatch to astropy pipeline or numpy fallback
    if _has_astropy() and _has_ccdproc():
        return _calibrate_astropy(
            str(raw_path), bias_path, dark_path, flat_path, output_path
        )
    else:
        return _calibrate_numpy(
            str(raw_path), bias_path, dark_path, flat_path, output_path
        )
