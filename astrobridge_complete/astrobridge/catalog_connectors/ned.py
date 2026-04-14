"""NASA Extragalactic Database (NED) connector.

Two implementations mirror the SIMBAD module pattern:

* ``NEDConnector``   – deterministic local dataset for CI / offline use.
* ``NedTapAdapter``  – live adapter for the NED TAP service (requires pyvo).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Callable, Optional, Protocol, TypeVar

from astrobridge.catalog_connectors import CatalogConnector
from astrobridge.catalog_connectors.simbad import _make_source
from astrobridge.geometry import angular_distance_arcsec
from astrobridge.models import Coordinate, Provenance, Source, Uncertainty

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class _TapProtocol(Protocol):
    def search(self, adql: str) -> Sequence[Any]: ...


# ---------------------------------------------------------------------------
# Local deterministic connector
# ---------------------------------------------------------------------------

_LOCAL_SOURCES = [
    _make_source(
        source_id="NED:PROXCEN-REF",
        name="ProxCen Reference",
        ra=217.4294,
        dec=-62.6803,
        magnitude=11.10,
        catalog_name="NED",
        catalog_version="local-1",
    ),
    _make_source(
        source_id="NED:M31",
        name="M31",
        ra=10.685,
        dec=41.269,
        magnitude=3.44,
        catalog_name="NED",
        catalog_version="local-1",
    ),
    _make_source(
        source_id="NED:GAL-18045",
        name="Galaxy 180+45",
        ra=180.0010,
        dec=44.9998,
        magnitude=15.80,
        catalog_name="NED",
        catalog_version="local-1",
    ),
    _make_source(
        source_id="NED:NGC5128",
        name="NGC 5128",
        ra=201.365,
        dec=-43.019,
        magnitude=7.84,
        catalog_name="NED",
        catalog_version="local-1",
    ),
]

_ALIASES: dict[str, str] = {
    "proxcen": "NED:PROXCEN-REF",
    "proximacentauri": "NED:PROXCEN-REF",
    "m31": "NED:M31",
    "andromedagalaxy": "NED:M31",
    "ngc5128": "NED:NGC5128",
}


class NEDConnector(CatalogConnector):
    """Deterministic local NED connector for development and CI."""

    def __init__(self) -> None:
        self._by_id: dict[str, Source] = {s.id: s for s in _LOCAL_SOURCES}

    def query_by_name(self, name: str) -> Optional[Source]:
        key = self._normalise_name(name)
        sid = _ALIASES.get(key)
        if sid:
            return self._by_id[sid].model_copy(deep=True)
        for src in _LOCAL_SOURCES:
            if key in self._normalise_name(src.name):
                return src.model_copy(deep=True)
        return None

    async def query_object(self, name: str) -> list[Source]:
        result = self.query_by_name(name)
        return [result] if result is not None else []

    async def cone_search(
        self, ra: float, dec: float, radius_arcsec: float
    ) -> list[Source]:
        if radius_arcsec <= 0:
            return []
        hits = [
            s.model_copy(deep=True)
            for s in _LOCAL_SOURCES
            if angular_distance_arcsec(s.coordinate.ra, s.coordinate.dec, ra, dec)
            <= radius_arcsec
        ]
        hits.sort(
            key=lambda s: angular_distance_arcsec(
                s.coordinate.ra, s.coordinate.dec, ra, dec
            )
        )
        return hits


# ---------------------------------------------------------------------------
# Live TAP adapter
# ---------------------------------------------------------------------------

class NedTapAdapter(CatalogConnector):
    """Live NED adapter backed by the NED TAP service."""

    DEFAULT_TAP_URL = "https://ned.ipac.caltech.edu/tap"

    def __init__(
        self,
        tap_url: str = DEFAULT_TAP_URL,
        max_records: int = 50,
        tap_service: Optional[_TapProtocol] = None,
        request_timeout_sec: float = 10.0,
        max_retries: int = 2,
        retry_delay_sec: float = 0.1,
        max_concurrency: int = 8,
    ) -> None:
        self.tap_url = tap_url
        self.max_records = max_records
        self.request_timeout_sec = request_timeout_sec
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

        if tap_service is not None:
            self._service: _TapProtocol = tap_service
        else:
            try:
                import pyvo  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RuntimeError(
                    "NedTapAdapter requires pyvo.  "
                    "Install with: pip install astrobridge[live]"
                ) from exc
            self._service = pyvo.dal.TAPService(self.tap_url)

    def query_by_name(self, name: str) -> Optional[Source]:
        rows = self._query_by_name_sync(name)
        return self._row_to_source(rows[0]) if rows else None

    async def query_object(self, name: str) -> list[Source]:
        try:
            return await self._run_io(self._query_object_sync, name)
        except asyncio.TimeoutError:
            logger.warning("NED TAP name query timed out for %s", name)
            return []

    async def cone_search(
        self, ra: float, dec: float, radius_arcsec: float
    ) -> list[Source]:
        try:
            return await self._run_io(self._cone_search_sync, ra, dec, radius_arcsec)
        except asyncio.TimeoutError:
            logger.warning("NED TAP cone search timed out at RA=%s Dec=%s", ra, dec)
            return []

    async def _run_io(self, func: Callable[..., _T], *args: Any) -> _T:
        async with self._semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args),
                timeout=self.request_timeout_sec,
            )

    def _query_object_sync(self, name: str) -> list[Source]:
        return [self._row_to_source(r) for r in self._query_by_name_sync(name)]

    def _query_by_name_sync(self, name: str) -> list[Any]:
        stripped = name.strip()
        if not stripped:
            return []
        try:
            escaped = self._escape_adql(stripped)
        except ValueError as exc:
            logger.warning("Unsafe name rejected for NED query: %s – %s", name, exc)
            return []
        adql = f"""
            SELECT TOP 1
                prefname AS main_id, ra, dec, pretype, uncmaja, uncmina
            FROM NEDTAP.objdir
            WHERE prefname = '{escaped}'
        """
        return self._search_with_retries(adql, context=f"name={name}")

    def _cone_search_sync(
        self, ra: float, dec: float, radius_arcsec: float
    ) -> list[Source]:
        if radius_arcsec <= 0:
            return []
        radius_deg = radius_arcsec / 3600.0
        adql = f"""
            SELECT TOP {int(self.max_records)}
                prefname AS main_id, ra, dec, pretype, uncmaja, uncmina
            FROM NEDTAP.objdir
            WHERE 1 = CONTAINS(
                POINT('ICRS', ra, dec),
                CIRCLE('ICRS', {ra}, {dec}, {radius_deg})
            )
        """
        rows = self._search_with_retries(adql, context="cone search")
        return [self._row_to_source(r) for r in rows]

    def _search_with_retries(self, adql: str, context: str) -> list[Any]:
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                return list(self._service.search(adql))
            except Exception as exc:
                if attempt == attempts - 1:
                    logger.warning(
                        "NED TAP %s failed after %d attempts: %s",
                        context,
                        attempts,
                        exc,
                    )
                    return []
                time.sleep(self.retry_delay_sec)
        return []

    @staticmethod
    def _val(row: Any, keys: list[str], default: Any = None) -> Any:
        for key in keys:
            try:
                v = row[key]
                if v is not None:
                    return v
            except (KeyError, TypeError):
                pass
            if hasattr(row, key):
                v = getattr(row, key, None)
                if v is not None:
                    return v
        return default

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _row_to_source(self, row: Any) -> Source:
        main_id = str(
            self._val(row, ["main_id", "MAIN_ID", "prefname", "PREFNAME"], "UNKNOWN")
        ).strip()
        ra = self._safe_float(self._val(row, ["ra", "RA"], 0.0), 0.0)
        dec = self._safe_float(self._val(row, ["dec", "DEC"], 0.0), 0.0)
        err_maj = self._safe_float(self._val(row, ["uncmaja", "UNCMAJA"]), 1.0)
        err_min = self._safe_float(self._val(row, ["uncmina", "UNCMINA"]), 1.0)

        return Source(
            id=f"NED_TAP:{main_id}",
            name=main_id,
            coordinate=Coordinate(ra=ra, dec=dec),
            uncertainty=Uncertainty(ra_error=err_maj, dec_error=err_min),
            photometry=[],
            provenance=Provenance(
                catalog_name="NED",
                catalog_version="tap-live",
                query_timestamp=datetime.utcnow(),
                source_id=main_id,
            ),
        )
