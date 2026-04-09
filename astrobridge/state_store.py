"""Shared helpers for SQLite-backed state persistence."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional


def resolve_state_db_path(db_path: Optional[str] = None) -> Path:
    """Resolve state DB path from explicit value or environment default."""
    default_path = Path(".astrobridge/state.db")
    selected = db_path if db_path is not None else os.getenv("ASTROBRIDGE_STATE_DB")
    resolved = Path(selected) if selected is not None else default_path
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    """Create a thread-safe SQLite connection for state stores."""
    return sqlite3.connect(str(db_path), check_same_thread=False)
