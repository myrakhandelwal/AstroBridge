"""Lightweight analytics tracking for educational and operational telemetry."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from astrobridge.state_store import resolve_state_db_path, connect_sqlite


class AnalyticsEvent(BaseModel):
    """Single analytics event emitted by clients or APIs."""

    event_type: str = Field(..., description="Event category such as query_submitted")
    query_type: Optional[str] = Field(None, description="Query kind when relevant")
    user_level: Optional[str] = Field(None, description="Beginner/intermediate/advanced")
    success: Optional[bool] = Field(None, description="Whether operation completed")
    latency_ms: Optional[float] = Field(None, ge=0, description="Observed latency in milliseconds")
    catalog_count: Optional[int] = Field(None, ge=0, description="Number of catalogs touched")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AnalyticsStore:
    """Event store with optional SQLite persistence and summary rollups."""

    def __init__(self, db_path: Optional[str] = None, persist: bool = True) -> None:
        self.persist = persist
        self._events: List[AnalyticsEvent] = []
        self._lock = threading.Lock()

        if self.persist:
            self._db_path = resolve_state_db_path(db_path)
            self._init_db()
        else:
            self._db_path = None

    def _connect(self) -> sqlite3.Connection:
        if self._db_path is None:
            raise RuntimeError("Persistence is disabled")
        return connect_sqlite(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    query_type TEXT,
                    user_level TEXT,
                    success INTEGER,
                    latency_ms REAL,
                    catalog_count INTEGER,
                    metadata_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> AnalyticsEvent:
        return AnalyticsEvent(
            event_type=row["event_type"],
            query_type=row["query_type"],
            user_level=row["user_level"],
            success=(None if row["success"] is None else bool(row["success"])),
            latency_ms=row["latency_ms"],
            catalog_count=row["catalog_count"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    def record(self, event: AnalyticsEvent) -> AnalyticsEvent:
        if self.persist:
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO analytics_events (
                            event_type,
                            query_type,
                            user_level,
                            success,
                            latency_ms,
                            catalog_count,
                            metadata_json,
                            timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event.event_type,
                            event.query_type,
                            event.user_level,
                            None if event.success is None else int(event.success),
                            event.latency_ms,
                            event.catalog_count,
                            json.dumps(event.metadata),
                            event.timestamp.isoformat(),
                        ),
                    )
                    conn.commit()
        else:
            # Even in non-persistent mode, protect list access with lock
            with self._lock:
                self._events.append(event)
        return event

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            if self.persist:
                with self._connect() as conn:
                    conn.execute("DELETE FROM analytics_events")
                    conn.commit()

    def list_events(self) -> List[AnalyticsEvent]:
        if not self.persist:
            with self._lock:
                return list(self._events)

        with self._lock:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT
                        event_type,
                        query_type,
                        user_level,
                        success,
                        latency_ms,
                        catalog_count,
                        metadata_json,
                        timestamp
                    FROM analytics_events
                    ORDER BY id ASC
                    """
                ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def summary(self) -> Dict[str, Any]:
        events = self.list_events()
        event_counts = Counter(evt.event_type for evt in events)
        query_events = [evt for evt in events if evt.query_type is not None]
        completed = [evt for evt in query_events if evt.success is not None]
        latencies = [evt.latency_ms for evt in query_events if evt.latency_ms is not None]

        success_rate = None
        if completed:
            successes = sum(1 for evt in completed if evt.success)
            success_rate = successes / len(completed)

        avg_latency_ms = None
        if latencies:
            avg_latency_ms = sum(latencies) / len(latencies)

        by_user_level = Counter(
            evt.user_level for evt in events if evt.user_level is not None
        )

        return {
            "total_events": len(events),
            "event_type_counts": dict(event_counts),
            "query_events": len(query_events),
            "query_success_rate": success_rate,
            "average_latency_ms": avg_latency_ms,
            "user_level_counts": dict(by_user_level),
        }
