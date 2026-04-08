"""Lightweight analytics tracking for educational and operational telemetry."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    """In-memory event store with summary rollups."""

    def __init__(self) -> None:
        self._events: List[AnalyticsEvent] = []

    def record(self, event: AnalyticsEvent) -> AnalyticsEvent:
        self._events.append(event)
        return event

    def clear(self) -> None:
        self._events.clear()

    def list_events(self) -> List[AnalyticsEvent]:
        return list(self._events)

    def summary(self) -> Dict[str, Any]:
        event_counts = Counter(evt.event_type for evt in self._events)
        query_events = [evt for evt in self._events if evt.query_type is not None]
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
            evt.user_level for evt in self._events if evt.user_level is not None
        )

        return {
            "total_events": len(self._events),
            "event_type_counts": dict(event_counts),
            "query_events": len(query_events),
            "query_success_rate": success_rate,
            "average_latency_ms": avg_latency_ms,
            "user_level_counts": dict(by_user_level),
        }
