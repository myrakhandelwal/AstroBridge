"""SQLite persistence layer for AstroBridge.

Uses raw SQL with parameterised queries throughout.  No ORM.  All public
functions receive a ``sqlite3.Connection`` so callers control transaction
boundaries and connection lifetime.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS objects (
    id              TEXT PRIMARY KEY,
    primary_name    TEXT NOT NULL,
    ra              REAL NOT NULL,
    dec             REAL NOT NULL,
    object_type     TEXT,
    ai_description  TEXT,
    last_updated    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id       TEXT NOT NULL REFERENCES objects(id),
    catalog_name    TEXT NOT NULL,
    source_json     TEXT NOT NULL,
    queried_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calibration_frames (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telescope_id    TEXT NOT NULL,
    frame_type      TEXT NOT NULL CHECK(frame_type IN ('bias','dark','flat')),
    date_obs        TEXT NOT NULL,
    fits_path       TEXT NOT NULL,
    UNIQUE(telescope_id, frame_type, date_obs)
);

CREATE INDEX IF NOT EXISTS idx_catalog_sources_object
    ON catalog_sources(object_id);

CREATE INDEX IF NOT EXISTS idx_calibration_telescope
    ON calibration_frames(telescope_id, frame_type);
"""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with row-factory and WAL mode enabled."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they do not already exist."""
    conn.executescript(_DDL)
    conn.commit()
    logger.debug("Database schema initialised")


def init_db(db_path: str) -> sqlite3.Connection:
    """Convenience: open connection and ensure schema exists."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    init_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# objects table
# ---------------------------------------------------------------------------

def upsert_object(
    conn: sqlite3.Connection,
    obj_id: str,
    primary_name: str,
    ra: float,
    dec: float,
    object_type: Optional[str] = None,
    ai_description: Optional[str] = None,
) -> None:
    """Insert or replace an object record."""
    conn.execute(
        """
        INSERT INTO objects (id, primary_name, ra, dec, object_type, ai_description, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            primary_name   = excluded.primary_name,
            ra             = excluded.ra,
            dec            = excluded.dec,
            object_type    = excluded.object_type,
            ai_description = COALESCE(excluded.ai_description, objects.ai_description),
            last_updated   = excluded.last_updated
        """,
        (
            obj_id,
            primary_name,
            ra,
            dec,
            object_type,
            ai_description,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()


def get_object(
    conn: sqlite3.Connection, obj_id: str
) -> Optional[dict[str, Any]]:
    """Fetch a single object row by primary key."""
    row = conn.execute(
        "SELECT * FROM objects WHERE id = ?", (obj_id,)
    ).fetchone()
    return dict(row) if row else None


def get_object_by_name(
    conn: sqlite3.Connection, name: str
) -> Optional[dict[str, Any]]:
    """Case-insensitive name lookup."""
    row = conn.execute(
        "SELECT * FROM objects WHERE LOWER(primary_name) = LOWER(?)", (name,)
    ).fetchone()
    return dict(row) if row else None


def update_ai_description(
    conn: sqlite3.Connection, obj_id: str, description: str
) -> None:
    """Persist a generated AI description; no-op if object doesn't exist."""
    conn.execute(
        "UPDATE objects SET ai_description = ?, last_updated = ? WHERE id = ?",
        (description, datetime.utcnow().isoformat(), obj_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# catalog_sources table
# ---------------------------------------------------------------------------

def insert_catalog_source(
    conn: sqlite3.Connection,
    object_id: str,
    catalog_name: str,
    source_data: dict[str, Any],
) -> None:
    """Persist a raw catalog record linked to an object."""
    conn.execute(
        """
        INSERT INTO catalog_sources (object_id, catalog_name, source_json, queried_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            object_id,
            catalog_name,
            json.dumps(source_data),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()


def get_catalog_sources(
    conn: sqlite3.Connection, object_id: str
) -> list[dict[str, Any]]:
    """Return all catalog entries linked to an object."""
    rows = conn.execute(
        "SELECT * FROM catalog_sources WHERE object_id = ? ORDER BY queried_at",
        (object_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# calibration_frames table
# ---------------------------------------------------------------------------

def register_calibration_frame(
    conn: sqlite3.Connection,
    telescope_id: str,
    frame_type: str,
    date_obs: str,
    fits_path: str,
) -> None:
    """Register a calibration frame path (bias / dark / flat)."""
    if frame_type not in ("bias", "dark", "flat"):
        raise ValueError(f"Invalid frame_type '{frame_type}'. Must be bias, dark, or flat.")
    conn.execute(
        """
        INSERT INTO calibration_frames (telescope_id, frame_type, date_obs, fits_path)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telescope_id, frame_type, date_obs) DO UPDATE SET
            fits_path = excluded.fits_path
        """,
        (telescope_id, frame_type, date_obs, fits_path),
    )
    conn.commit()


def get_calibration_frame(
    conn: sqlite3.Connection,
    telescope_id: str,
    frame_type: str,
    date_obs: str,
) -> Optional[str]:
    """Return the FITS path for a calibration frame, or None if not found."""
    row = conn.execute(
        """
        SELECT fits_path FROM calibration_frames
        WHERE telescope_id = ? AND frame_type = ? AND date_obs = ?
        """,
        (telescope_id, frame_type, date_obs),
    ).fetchone()
    return row["fits_path"] if row else None


def list_calibration_frames(
    conn: sqlite3.Connection,
    telescope_id: str,
) -> list[dict[str, Any]]:
    """Return all calibration frames for a telescope."""
    rows = conn.execute(
        "SELECT * FROM calibration_frames WHERE telescope_id = ? ORDER BY date_obs",
        (telescope_id,),
    ).fetchall()
    return [dict(r) for r in rows]
