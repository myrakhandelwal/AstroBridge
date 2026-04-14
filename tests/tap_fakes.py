"""Shared TAP test doubles used across adapter tests."""

from __future__ import annotations

from typing import Any, Sequence


class FakeRow(dict[str, object]):
    """Simple row object matching minimal TAP row behavior."""

    @property
    def colnames(self) -> list[str]:
        return list(self.keys())


class FakeTapService:
    """Captures ADQL and returns sequential deterministic responses."""

    def __init__(self, responses: Sequence[Any]):
        self.responses = list(responses)
        self.queries: list[str] = []

    def search(self, adql: str) -> Any:
        self.queries.append(adql)
        if not self.responses:
            return []
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class StaticTapService:
    """Returns a stable row set on every call and records queries."""

    def __init__(self, rows: Sequence[dict[str, object]]):
        self._rows = [FakeRow(row) for row in rows]
        self.queries: list[str] = []

    def search(self, adql: str) -> list[FakeRow]:
        self.queries.append(adql)
        return self._rows
