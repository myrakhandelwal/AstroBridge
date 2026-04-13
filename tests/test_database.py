"""Tests for astrobridge.database — SQLite persistence layer."""
import sqlite3

import pytest

from astrobridge.database import (
    get_calibration_frame,
    get_object,
    get_object_by_name,
    init_db,
    init_schema,
    insert_catalog_source,
    list_calibration_frames,
    register_calibration_frame,
    update_ai_description,
    upsert_object,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    connection = init_db(db_path)
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def test_init_schema_creates_tables(tmp_path):
    db = str(tmp_path / "schema_test.db")
    c = init_db(db)
    tables = {
        row[0]
        for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"objects", "catalog_sources", "calibration_frames"}.issubset(tables)
    c.close()


def test_init_schema_idempotent(conn):
    """Running init_schema twice must not raise."""
    init_schema(conn)


# ---------------------------------------------------------------------------
# objects table
# ---------------------------------------------------------------------------

def test_upsert_and_get_object(conn):
    upsert_object(conn, "obj-1", "Proxima Centauri", 217.429, -62.680)
    row = get_object(conn, "obj-1")
    assert row is not None
    assert row["primary_name"] == "Proxima Centauri"
    assert abs(row["ra"] - 217.429) < 1e-6


def test_upsert_updates_existing(conn):
    upsert_object(conn, "obj-2", "Old Name", 10.0, 20.0)
    upsert_object(conn, "obj-2", "New Name", 10.0, 20.0)
    row = get_object(conn, "obj-2")
    assert row["primary_name"] == "New Name"


def test_get_object_missing(conn):
    assert get_object(conn, "nonexistent") is None


def test_get_object_by_name_case_insensitive(conn):
    upsert_object(conn, "obj-3", "Sirius", 101.287, -16.716)
    row = get_object_by_name(conn, "sirius")
    assert row is not None
    assert row["id"] == "obj-3"


def test_get_object_by_name_missing(conn):
    assert get_object_by_name(conn, "does_not_exist") is None


def test_update_ai_description(conn):
    upsert_object(conn, "obj-4", "M31", 10.685, 41.269)
    update_ai_description(conn, "obj-4", "Andromeda is a spiral galaxy.")
    row = get_object(conn, "obj-4")
    assert row["ai_description"] == "Andromeda is a spiral galaxy."


def test_update_ai_description_noop_for_missing(conn):
    """Should silently do nothing when the object id doesn't exist."""
    update_ai_description(conn, "ghost-id", "ignored")


def test_upsert_preserves_ai_description_on_null(conn):
    """Re-upserting without a description should keep the existing one."""
    upsert_object(conn, "obj-5", "Vega", 279.235, 38.784, ai_description="Bright A-type star.")
    upsert_object(conn, "obj-5", "Vega", 279.235, 38.784)  # no ai_description
    row = get_object(conn, "obj-5")
    assert row["ai_description"] == "Bright A-type star."


# ---------------------------------------------------------------------------
# catalog_sources table
# ---------------------------------------------------------------------------

def test_insert_and_retrieve_catalog_source(conn):
    upsert_object(conn, "obj-6", "Betelgeuse", 88.793, 7.407)
    insert_catalog_source(conn, "obj-6", "SIMBAD", {"mag_V": 0.42, "type": "star"})
    from astrobridge.database import get_catalog_sources
    sources = get_catalog_sources(conn, "obj-6")
    assert len(sources) == 1
    import json
    data = json.loads(sources[0]["source_json"])
    assert data["mag_V"] == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# calibration_frames table
# ---------------------------------------------------------------------------

def test_register_and_get_calibration_frame(conn):
    register_calibration_frame(conn, "keck-lris", "bias", "2026-04-13", "/data/bias.fits")
    path = get_calibration_frame(conn, "keck-lris", "bias", "2026-04-13")
    assert path == "/data/bias.fits"


def test_get_calibration_frame_missing(conn):
    assert get_calibration_frame(conn, "vlt-fors2", "flat", "2026-01-01") is None


def test_register_calibration_frame_upsert(conn):
    register_calibration_frame(conn, "keck-lris", "dark", "2026-04-13", "/old/dark.fits")
    register_calibration_frame(conn, "keck-lris", "dark", "2026-04-13", "/new/dark.fits")
    path = get_calibration_frame(conn, "keck-lris", "dark", "2026-04-13")
    assert path == "/new/dark.fits"


def test_invalid_frame_type_raises(conn):
    with pytest.raises(ValueError, match="Invalid frame_type"):
        register_calibration_frame(conn, "keck", "science", "2026-04-13", "/path.fits")


def test_list_calibration_frames(conn):
    register_calibration_frame(conn, "vlt", "bias", "2026-04-10", "/b1.fits")
    register_calibration_frame(conn, "vlt", "flat", "2026-04-10", "/f1.fits")
    register_calibration_frame(conn, "keck", "bias", "2026-04-10", "/b2.fits")
    frames = list_calibration_frames(conn, "vlt")
    assert len(frames) == 2
    assert all(f["telescope_id"] == "vlt" for f in frames)
