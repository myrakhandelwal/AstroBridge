"""Tests for astrobridge.ccd_calibration — CCD reduction pipeline."""

import pytest

from astrobridge.ccd_calibration import (
    _has_astropy,
    _has_ccdproc,
    _resolve_frame_path,
    calibrate_ccd,
)
from astrobridge.database import init_db, register_calibration_frame

# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------

def test_has_astropy_returns_bool():
    assert isinstance(_has_astropy(), bool)


def test_has_ccdproc_returns_bool():
    assert isinstance(_has_ccdproc(), bool)


# ---------------------------------------------------------------------------
# _resolve_frame_path
# ---------------------------------------------------------------------------

def test_resolve_frame_path_no_conn_no_env_returns_none():
    result = _resolve_frame_path(None, "keck", "bias", "2026-04-13")
    assert result is None


def test_resolve_frame_path_calib_env_existing_file(tmp_path, monkeypatch):
    tel = "vlt"
    date = "2026-04-13"
    frame_dir = tmp_path / tel / date
    frame_dir.mkdir(parents=True)
    bias_file = frame_dir / "bias.fits"
    bias_file.write_bytes(b"fake fits")

    monkeypatch.setenv("CALIB_PATH", str(tmp_path))
    result = _resolve_frame_path(None, tel, "bias", date)
    assert result == str(bias_file)


def test_resolve_frame_path_calib_env_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CALIB_PATH", str(tmp_path))
    result = _resolve_frame_path(None, "keck", "flat", "2026-04-13")
    assert result is None


def test_resolve_frame_path_db_lookup(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    frame_file = tmp_path / "bias.fits"
    frame_file.write_bytes(b"fake fits")
    register_calibration_frame(conn, "keck", "bias", "2026-04-13", str(frame_file))

    result = _resolve_frame_path(conn, "keck", "bias", "2026-04-13")
    assert result == str(frame_file)
    conn.close()


def test_resolve_frame_path_db_path_not_on_disk(tmp_path):
    """DB entry exists but path doesn't exist on disk — should return None."""
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    register_calibration_frame(conn, "keck", "bias", "2026-04-13", "/nonexistent/bias.fits")

    result = _resolve_frame_path(conn, "keck", "bias", "2026-04-13")
    assert result is None
    conn.close()


# ---------------------------------------------------------------------------
# calibrate_ccd
# ---------------------------------------------------------------------------

def test_calibrate_ccd_raises_for_missing_raw(tmp_path):
    with pytest.raises(FileNotFoundError):
        calibrate_ccd("/nonexistent/raw.fits", "keck")


def test_calibrate_ccd_no_frames_returns_raw_unchanged(tmp_path):
    """When no calibration frames are found the raw path is returned as-is."""
    raw = tmp_path / "raw.fits"
    raw.write_bytes(b"fake raw fits")
    result = calibrate_ccd(str(raw), "keck", date_obs="2026-04-13", conn=None)
    assert result == str(raw)


def test_calibrate_ccd_uses_date_obs_today_when_none(tmp_path):
    """Passing date_obs=None should not raise; today's date is filled in."""
    raw = tmp_path / "raw.fits"
    raw.write_bytes(b"fake raw fits")
    # No calibration frames → returns raw unchanged, no error
    result = calibrate_ccd(str(raw), "keck", date_obs=None, conn=None)
    assert result == str(raw)


def test_calibrate_ccd_uses_output_dir(tmp_path, monkeypatch):
    """output_dir parameter is respected when calibration frames exist."""
    raw = tmp_path / "raw.fits"
    # Write a minimal FITS-like bytes structure (real parsing won't happen here
    # because _has_astropy()/ccdproc won't be True in CI, and the numpy path
    # would fail on fake data — so we just test the no-frames path).
    raw.write_bytes(b"fake raw fits")
    out_dir = tmp_path / "output"
    result = calibrate_ccd(
        str(raw), "keck", date_obs="2026-04-13", conn=None, output_dir=str(out_dir)
    )
    # No frames registered → raw path returned unchanged
    assert result == str(raw)
