"""SIMBAD catalog connector.

Two implementations are provided:

* ``SimbadConnector``  – deterministic, network-free local dataset used for
  development and CI.  Responds correctly for Proxima Centauri and a handful
  of test objects.

* ``SimbadTapAdapter`` – live adapter that queries the SIMBAD TAP service via
  pyvo (optional ``[live]`` extra).  Accepts an injected ``tap_service`` for
  unit-testing without network access.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Callable, Optional, Protocol, TypeVar

from astrobridge.catalog_connectors import CatalogConnector
from astrobridge.geometry import angular_distance_arcsec
from astrobridge.models import Coordinate, Photometry, Provenance, Source, Uncertainty

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class _TapProtocol(Protocol):
    def search(self, adql: str) -> Sequence[Any]: ...


# ---------------------------------------------------------------------------
# Shared factory helper
# ---------------------------------------------------------------------------

def _make_source(
    *,
    source_id: str,
    name: str,
    ra: float,
    dec: float,
    magnitude: float,
    catalog_name: str = "SIMBAD",
    catalog_version: str = "local-1",
) -> Source:
    return Source(
        id=source_id,
        name=name,
        coordinate=Coordinate(ra=ra, dec=dec),
        uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
        photometry=[Photometry(magnitude=magnitude, band="V")],
        provenance=Provenance(
            catalog_name=catalog_name,
            catalog_version=catalog_version,
            query_timestamp=datetime.utcnow(),
            source_id=source_id,
        ),
    )


# ---------------------------------------------------------------------------
# Local deterministic connector
# ---------------------------------------------------------------------------

_LOCAL_SOURCES = [
    _make_source(
        source_id="SIMBAD:PROXCEN",
        name="Proxima Centauri",
        ra=217.429,
        dec=-62.680,
        magnitude=11.05,
    ),
    _make_source(
        source_id="SIMBAD:SIRIUS",
        name="Sirius",
        ra=101.287,
        dec=-16.716,
        magnitude=-1.46,
    ),
    _make_source(
        source_id="SIMBAD:VEGA",
        name="Vega",
        ra=279.235,
        dec=38.783,
        magnitude=0.03,
    ),
    _make_source(
        source_id="SIMBAD:BETELGEUSE",
        name="Betelgeuse",
        ra=88.792,
        dec=7.407,
        magnitude=0.58,
    ),
    _make_source(
        source_id="SIMBAD:M31",
        name="M31",
        ra=10.685,
        dec=41.269,
        magnitude=3.44,
        catalog_name="SIMBAD",
    ),
    _make_source(
        source_id="SIMBAD:FIELD-180+45",
        name="Field Star 180+45",
        ra=180.0008,
        dec=45.0007,
        magnitude=13.20,
    ),
]

_ALIASES: dict[str, str] = {
    "proxcen": "SIMBAD:PROXCEN",
    "proximacentauri": "SIMBAD:PROXCEN",
    "sirius": "SIMBAD:SIRIUS",
    "vega": "SIMBAD:VEGA",
    "betelgeuse": "SIMBAD:BETELGEUSE",
    "m31": "SIMBAD:M31",
    "andromedagalaxy": "SIMBAD:M31",
}


class SimbadConnector(CatalogConnector):
    """Deterministic local SIMBAD connector.

    Sufficient for offline development; swap for ``SimbadTapAdapter`` in
    production.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, Source] = {s.id: s for s in _LOCAL_SOURCES}

    # ------------------------------------------------------------------
    # CatalogConnector interface
    # ------------------------------------------------------------------

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

class SimbadTapAdapter(CatalogConnector):
    """Live SIMBAD adapter backed by the SIMBAD TAP service.

    Requires the ``[live]`` extra (``pip install astrobridge[live]``).

    Parameters
    ----------
    tap_url :
        SIMBAD TAP endpoint.  Override only for testing.
    max_records :
        Row cap for cone-search results.
    tap_service :
        Injected TAP service (accepts any object with a ``.search(adql)``
        method).  Used in unit tests so no real network call is needed.
    request_timeout_sec :
        Per-call timeout enforced by ``asyncio.wait_for``.
    max_retries :
        Number of retry attempts on failure before giving up.
    retry_delay_sec :
        Sleep between retries.
    max_concurrency :
        Maximum simultaneous in-flight TAP requests.
    """

    DEFAULT_TAP_URL = "https://simbad.cds.unistra.fr/simbad/sim-tap"

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
                    "SimbadTapAdapter requires pyvo.  "
                    "Install with: pip install astrobridge[live]"
                ) from exc
            self._service = pyvo.dal.TAPService(self.tap_url)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def query_by_name(self, name: str) -> Optional[Source]:
        rows = self._query_by_name_sync(name)
        return self._row_to_source(rows[0]) if rows else None

    async def query_object(self, name: str) -> list[Source]:
        try:
            return await self._run_io(self._query_by_name_sync, name)
        except asyncio.TimeoutError:
            logger.warning("SIMBAD TAP name query timed out for %s", name)
            return []

    async def cone_search(
        self, ra: float, dec: float, radius_arcsec: float
    ) -> list[Source]:
        try:
            return await self._run_io(self._cone_search_sync, ra, dec, radius_arcsec)
        except asyncio.TimeoutError:
            logger.warning(
                "SIMBAD TAP cone search timed out at RA=%s Dec=%s", ra, dec
            )
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_io(self, func: Callable[..., _T], *args: Any) -> _T:
        async with self._semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args),
                timeout=self.request_timeout_sec,
            )

    def _query_by_name_sync(self, name: str) -> list[Any]:
        stripped = name.strip()
        if not stripped:
            return []
        try:
            escaped = self._escape_adql(stripped)
        except ValueError as exc:
            logger.warning("Unsafe name rejected for SIMBAD query: %s – %s", name, exc)
            return []
        adql = f"""
            SELECT TOP 1
                b.main_id, b.ra, b.dec,
                b.coo_err_maj, b.coo_err_min, f.flux
            FROM basic AS b
            LEFT OUTER JOIN flux AS f ON b.oid = f.oidref AND f.filter = 'V'
            INNER JOIN ident AS i ON b.oid = i.oidref
            WHERE i.id = '{escaped}'
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
                b.main_id, b.ra, b.dec,
                b.coo_err_maj, b.coo_err_min, f.flux
            FROM basic AS b
            LEFT OUTER JOIN flux AS f ON b.oid = f.oidref AND f.filter = 'V'
            WHERE 1 = CONTAINS(
                POINT('ICRS', b.ra, b.dec),
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
                        "SIMBAD TAP %s failed after %d attempts: %s",
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
        main_id = str(self._val(row, ["main_id", "MAIN_ID"], "UNKNOWN")).strip()
        ra = self._safe_float(self._val(row, ["ra", "RA"], 0.0), 0.0)
        dec = self._safe_float(self._val(row, ["dec", "DEC"], 0.0), 0.0)
        err_maj = self._safe_float(self._val(row, ["coo_err_maj", "COO_ERR_MAJ"]), 0.5)
        err_min = self._safe_float(self._val(row, ["coo_err_min", "COO_ERR_MIN"]), 0.5)
        flux_v = self._val(row, ["flux", "FLUX"])

        photometry: list[Photometry] = []
        if flux_v is not None:
            with contextlib.suppress(TypeError, ValueError):
                photometry = [Photometry(magnitude=float(flux_v), band="V")]

        return Source(
            id=f"SIMBAD_TAP:{main_id}",
            name=main_id,
            coordinate=Coordinate(ra=ra, dec=dec),
            uncertainty=Uncertainty(ra_error=err_maj, dec_error=err_min),
            photometry=photometry,
            provenance=Provenance(
                catalog_name="SIMBAD",
                catalog_version="tap-live",
                query_timestamp=datetime.utcnow(),
                source_id=main_id,
            ),
        )
