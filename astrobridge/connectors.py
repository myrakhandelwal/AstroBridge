"""External catalog connectors."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Callable, Optional, Protocol, TypeVar

from .geometry import angular_distance_arcsec
from .models import Coordinate, Photometry, Provenance, Source, Uncertainty

logger = logging.getLogger(__name__)


class TapServiceProtocol(Protocol):
    def search(self, adql: str) -> Sequence[Any]:
        ...


_T = TypeVar("_T")


class CatalogConnector(ABC):
    """Base class for catalog connectors."""
    
    @abstractmethod
    def query(self, name: str) -> Optional[Source]:
        """Query catalog for a source."""
        raise NotImplementedError

    async def query_object(self, name: str) -> list[Source]:
        """Async-compatible object lookup used by integration paths."""
        result = self.query(name)
        return [result] if result is not None else []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        """Async-compatible cone search placeholder for future live catalog queries."""
        return []

    @staticmethod
    def _normalized_name(name: str) -> str:
        """Normalize object names for robust matching.
        
        Removes whitespace and special characters, converts to lowercase.
        
        Args:
            name: Object name to normalize.
            
        Returns:
            Normalized alphanumeric lowercase name.
        """
        return "".join(ch.lower() for ch in name if ch.isalnum())

    @staticmethod
    def _distance_arcsec(coord1: Coordinate, coord2: Coordinate) -> float:
        """Compute simple angular separation in arcseconds.
        
        Uses flat-sky approximation (Euclidean distance in RA/Dec space).
        Appropriate for small separations where |Δ| < a few degrees.
        
        Args:
            coord1: First coordinate.
            coord2: Second coordinate.
            
        Returns:
            Angular separation in arcseconds.
        """
        return angular_distance_arcsec(
            coord1.ra,
            coord1.dec,
            coord2.ra,
            coord2.dec,
        )

    @staticmethod
    def _escape_adql_string(value: str) -> str:
        """Safely escape a string for use in ADQL queries.
        
        ADQL uses single quotes, so we escape them by doubling.
        Additionally, validates the string contains only safe characters.
        
        Args:
            value: String to escape for ADQL.
            
        Returns:
            Properly escaped ADQL string literal (without quotes).
            
        Raises:
            ValueError: If string contains potentially dangerous patterns.
        """
        # First, check for potentially dangerous patterns
        dangerous_patterns = ['--', '/*', '*/', ';', '\x00']
        value_lower = value.lower()
        for pattern in dangerous_patterns:
            if pattern in value_lower:
                raise ValueError(
                    f"String contains potentially dangerous pattern: {pattern}"
                )
        
        # Escape single quotes by doubling them (ADQL standard)
        return value.replace("'", "''")


def _build_source(
    *,
    source_id: str,
    name: str,
    ra: float,
    dec: float,
    magnitude: float,
    catalog_name: str,
    catalog_version: str,
) -> Source:
    """Create a deterministic Source object for local connector datasets.
    
    Used by deterministic connectors (SIMBAD, NED) that return
    synthetic data for testing and demo purposes.
    
    Args:
        source_id: Unique identifier in source catalog.
        name: Human-readable source name.
        ra: Right ascension in degrees.
        dec: Declination in degrees.
        magnitude: Apparent magnitude in V-band.
        catalog_name: Name of origin catalog.
        catalog_version: Version string of catalog.
        
    Returns:
        Fully instantiated Source object.
    """
    return Source(
        id=source_id,
        name=name,
        coordinate=Coordinate(
            ra=ra,
            dec=dec,
            pm_ra_mas_per_year=None,
            pm_dec_mas_per_year=None,
        ),
        uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
        photometry=[Photometry(magnitude=magnitude, band="V", magnitude_error=None)],
        provenance=Provenance(
            catalog_name=catalog_name,
            catalog_version=catalog_version,
            query_timestamp=datetime.utcnow(),
            source_id=source_id,
        ),
    )


class SimbadConnector(CatalogConnector):
    """SIMBAD catalog connector."""

    def __init__(self) -> None:
        self._sources = [
            _build_source(
                source_id="SIMBAD:PROXCEN",
                name="Proxima Centauri",
                ra=217.429,
                dec=-62.680,
                magnitude=11.05,
                catalog_name="SIMBAD",
                catalog_version="local-1",
            ),
            _build_source(
                source_id="SIMBAD:FIELDSTAR-1",
                name="Field Star 180+45",
                ra=180.0008,
                dec=45.0007,
                magnitude=13.20,
                catalog_name="SIMBAD",
                catalog_version="local-1",
            ),
        ]
        self._aliases = {
            "proxcen": "SIMBAD:PROXCEN",
            "proximacentauri": "SIMBAD:PROXCEN",
        }
        self._by_id = {source.id: source for source in self._sources}
    
    def query(self, name: str) -> Optional[Source]:
        """Query SIMBAD for a source."""
        normalized = self._normalized_name(name)
        if not normalized:
            return None

        source_id = self._aliases.get(normalized)
        if source_id:
            return self._by_id[source_id].model_copy(deep=True)

        for source in self._sources:
            if normalized in self._normalized_name(source.name):
                return source.model_copy(deep=True)

        return None

    async def query_object(self, name: str) -> list[Source]:
        """Return SIMBAD sources for an object query."""
        result = self.query(name)
        return [result] if result is not None else []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        """Return all SIMBAD sources within the specified radius."""
        if radius_arcsec <= 0:
            return []

        matches = []
        for source in self._sources:
            separation = self._distance_arcsec(source.coordinate, coordinate)
            if separation <= radius_arcsec:
                matches.append(source.model_copy(deep=True))

        matches.sort(
            key=lambda src: self._distance_arcsec(src.coordinate, coordinate)
        )
        return matches


class NEDConnector(CatalogConnector):
    """NASA Extragalactic Database connector."""

    def __init__(self) -> None:
        self._sources = [
            _build_source(
                source_id="NED:PROXCEN-REF",
                name="ProxCen Reference",
                ra=217.4294,
                dec=-62.6803,
                magnitude=11.10,
                catalog_name="NED",
                catalog_version="local-1",
            ),
            _build_source(
                source_id="NED:GAL-18045",
                name="Galaxy 180+45",
                ra=180.0010,
                dec=44.9998,
                magnitude=15.80,
                catalog_name="NED",
                catalog_version="local-1",
            ),
        ]
        self._aliases = {
            "proxcen": "NED:PROXCEN-REF",
            "proximacentauri": "NED:PROXCEN-REF",
        }
        self._by_id = {source.id: source for source in self._sources}
    
    def query(self, name: str) -> Optional[Source]:
        """Query NED for a source."""
        normalized = self._normalized_name(name)
        if not normalized:
            return None

        source_id = self._aliases.get(normalized)
        if source_id:
            return self._by_id[source_id].model_copy(deep=True)

        for source in self._sources:
            if normalized in self._normalized_name(source.name):
                return source.model_copy(deep=True)

        return None

    async def query_object(self, name: str) -> list[Source]:
        """Return NED sources for an object query."""
        result = self.query(name)
        return [result] if result is not None else []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        """Return all NED sources within the specified radius."""
        if radius_arcsec <= 0:
            return []

        matches = []
        for source in self._sources:
            separation = self._distance_arcsec(source.coordinate, coordinate)
            if separation <= radius_arcsec:
                matches.append(source.model_copy(deep=True))

        matches.sort(
            key=lambda src: self._distance_arcsec(src.coordinate, coordinate)
        )
        return matches


class SimbadTapAdapter(CatalogConnector):
    """Live SIMBAD adapter backed by the SIMBAD TAP service."""

    DEFAULT_TAP_URL = "https://simbad.cds.unistra.fr/simbad/sim-tap"

    def __init__(
        self,
        tap_url: str = DEFAULT_TAP_URL,
        max_records: int = 50,
        tap_service: Optional[TapServiceProtocol] = None,
        request_timeout_sec: float = 10.0,
        max_retries: int = 2,
        retry_delay_sec: float = 0.1,
        max_concurrency: int = 8,
    ):
        """Initialize the TAP adapter.

        Args:
            tap_url: SIMBAD TAP endpoint URL
            max_records: Maximum rows returned by cone search
            tap_service: Optional injected TAP service for testing
            request_timeout_sec: Timeout for async TAP calls
            max_retries: Number of retries after an initial failed attempt
            retry_delay_sec: Delay between retries in seconds
            max_concurrency: Maximum concurrent in-flight TAP requests
        """
        self.tap_url = tap_url
        self.max_records = max_records
        self.request_timeout_sec = request_timeout_sec
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self._request_semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._service: TapServiceProtocol

        if tap_service is not None:
            self._service = tap_service
            return

        try:
            import pyvo as _pyvo  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "SimbadTapAdapter requires pyvo. Install with `pip install -e .[live]`."
            ) from exc

        self._service = _pyvo.dal.TAPService(self.tap_url)

    def query(self, name: str) -> Optional[Source]:
        """Query SIMBAD TAP by object identifier."""
        results = self._query_by_name(name)
        if not results:
            return None
        return self._row_to_source(results[0])

    async def query_object(self, name: str) -> list[Source]:
        """Async object lookup against SIMBAD TAP."""
        try:
            return await self._run_io_bound(self._query_object_sync, name)
        except asyncio.TimeoutError:
            logger.warning("SIMBAD TAP name query timed out for %s", name)
            return []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        """Async cone search against SIMBAD TAP."""
        try:
            return await self._run_io_bound(self._cone_search_sync, coordinate, radius_arcsec)
        except asyncio.TimeoutError:
            logger.warning(
                "SIMBAD TAP cone search timed out at RA=%s Dec=%s",
                coordinate.ra,
                coordinate.dec,
            )
            return []

    async def _run_io_bound(self, func: Callable[..., _T], *args: Any) -> _T:
        """Run blocking TAP I/O in a bounded worker thread."""
        async with self._request_semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args),
                timeout=self.request_timeout_sec,
            )

    def _query_object_sync(self, name: str) -> list[Source]:
        rows = self._query_by_name(name)
        return [self._row_to_source(row) for row in rows]

    def _cone_search_sync(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        if radius_arcsec <= 0:
            return []

        radius_deg = radius_arcsec / 3600.0
        adql = f"""
            SELECT TOP {int(self.max_records)}
                b.main_id,
                b.ra,
                b.dec,
                b.coo_err_maj,
                b.coo_err_min,
                f.flux
            FROM basic AS b
            LEFT OUTER JOIN flux AS f ON b.oid = f.oidref AND f.filter = 'V'
            WHERE 1 = CONTAINS(
                POINT('ICRS', b.ra, b.dec),
                CIRCLE('ICRS', {coordinate.ra}, {coordinate.dec}, {radius_deg})
            )
        """

        rows = self._search_with_retries(adql, context="cone search")
        return [self._row_to_source(row) for row in rows]

    def _query_by_name(self, name: str) -> list[Any]:
        normalized = name.strip()
        if not normalized:
            return []

        try:
            escaped_name = self._escape_adql_string(normalized)
        except ValueError as exc:
            logger.warning("Invalid object name for SIMBAD query: %s - %s", name, exc)
            return []
            
        adql = f"""
            SELECT TOP 1
                b.main_id,
                b.ra,
                b.dec,
                b.coo_err_maj,
                b.coo_err_min,
                f.flux
            FROM basic AS b
            LEFT OUTER JOIN flux AS f ON b.oid = f.oidref AND f.filter = 'V'
            INNER JOIN ident AS i ON b.oid = i.oidref
            WHERE i.id = '{escaped_name}'
        """

        return self._search_with_retries(adql, context=f"name query for {name}")

    @staticmethod
    def _value(row: Any, keys: list[str], default: Any = None) -> Any:
        """Read first available key from TAP row using common key aliases.
        
        Attempts to access row using bracket notation, then attribute access,
        and returns the first successfully retrieved value.
        """
        for key in keys:
            value = None
            found = False
            try:
                value = row[key]
                found = True
            except (KeyError, TypeError):
                # KeyError: dict-like object doesn't have the key
                # TypeError: object doesn't support item access
                pass

            if not found and hasattr(row, key):
                try:
                    value = getattr(row, key)
                    found = True
                except AttributeError:
                    pass

            if found and value is not None:
                return value
        return default

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        """Convert value to float with a safe default fallback."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _search_with_retries(self, adql: str, context: str) -> list[Any]:
        """Execute TAP query with retry-on-failure behavior."""
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                table = self._service.search(adql)
                return list(table)
            except Exception as exc:
                if attempt == attempts - 1:
                    logger.warning("SIMBAD TAP %s failed after retries: %s", context, exc)
                    return []
                time.sleep(self.retry_delay_sec)
        return []

    def _row_to_source(self, row: Any) -> Source:
        main_id = str(self._value(row, ["main_id", "MAIN_ID"], "UNKNOWN")).strip()
        ra = self._safe_float(self._value(row, ["ra", "RA"], 0.0), 0.0)
        dec = self._safe_float(self._value(row, ["dec", "DEC"], 0.0), 0.0)
        # Use _value with None default, let _safe_float handle conversion with proper fallback
        # This avoids the "or 0.5" pattern which treats 0.0 as falsy and loses valid values
        err_maj = self._safe_float(self._value(row, ["coo_err_maj", "COO_ERR_MAJ"], None), 0.5)
        err_min = self._safe_float(self._value(row, ["coo_err_min", "COO_ERR_MIN"], None), 0.5)
        flux_v = self._value(row, ["flux", "FLUX"], None)

        photometry = []
        if flux_v is not None:
            try:
                photometry = [Photometry(magnitude=float(flux_v), band="V", magnitude_error=None)]
            except (TypeError, ValueError):
                photometry = []

        return Source(
            id=f"SIMBAD_TAP:{main_id}",
            name=main_id,
            coordinate=Coordinate(
                ra=ra,
                dec=dec,
                pm_ra_mas_per_year=None,
                pm_dec_mas_per_year=None,
            ),
            uncertainty=Uncertainty(ra_error=err_maj, dec_error=err_min),
            photometry=photometry,
            provenance=Provenance(
                catalog_name="SIMBAD",
                catalog_version="tap-live",
                query_timestamp=datetime.utcnow(),
                source_id=main_id,
            ),
        )


class NedTapAdapter(CatalogConnector):
    """Live NED adapter backed by a TAP service endpoint."""

    DEFAULT_TAP_URL = "https://ned.ipac.caltech.edu/tap"

    def __init__(
        self,
        tap_url: str = DEFAULT_TAP_URL,
        max_records: int = 50,
        tap_service: Optional[TapServiceProtocol] = None,
        request_timeout_sec: float = 10.0,
        max_retries: int = 2,
        retry_delay_sec: float = 0.1,
        max_concurrency: int = 8,
    ):
        """Initialize the NED TAP adapter.

        Args:
            tap_url: NED TAP endpoint URL
            max_records: Maximum rows returned by cone search
            tap_service: Optional injected TAP service for testing
            request_timeout_sec: Timeout for async TAP calls
            max_retries: Number of retries after an initial failed attempt
            retry_delay_sec: Delay between retries in seconds
            max_concurrency: Maximum concurrent in-flight TAP requests
        """
        self.tap_url = tap_url
        self.max_records = max_records
        self.request_timeout_sec = request_timeout_sec
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self._request_semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._service: TapServiceProtocol

        if tap_service is not None:
            self._service = tap_service
            return

        try:
            import pyvo as _pyvo
        except ImportError as exc:
            raise RuntimeError(
                "NedTapAdapter requires pyvo. Install with `pip install -e .[live]`."
            ) from exc

        self._service = _pyvo.dal.TAPService(self.tap_url)

    def query(self, name: str) -> Optional[Source]:
        """Query NED TAP by object identifier."""
        rows = self._query_by_name(name)
        if not rows:
            return None
        return self._row_to_source(rows[0])

    async def query_object(self, name: str) -> list[Source]:
        """Async object lookup against NED TAP."""
        try:
            return await self._run_io_bound(self._query_object_sync, name)
        except asyncio.TimeoutError:
            logger.warning("NED TAP name query timed out for %s", name)
            return []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        """Async cone search against NED TAP."""
        try:
            return await self._run_io_bound(self._cone_search_sync, coordinate, radius_arcsec)
        except asyncio.TimeoutError:
            logger.warning(
                "NED TAP cone search timed out at RA=%s Dec=%s",
                coordinate.ra,
                coordinate.dec,
            )
            return []

    async def _run_io_bound(self, func: Callable[..., _T], *args: Any) -> _T:
        """Run blocking TAP I/O in a bounded worker thread."""
        async with self._request_semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args),
                timeout=self.request_timeout_sec,
            )

    def _query_object_sync(self, name: str) -> list[Source]:
        rows = self._query_by_name(name)
        return [self._row_to_source(row) for row in rows]

    def _cone_search_sync(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        if radius_arcsec <= 0:
            return []

        radius_deg = radius_arcsec / 3600.0
        adql = f"""
            SELECT TOP {int(self.max_records)}
                prefname AS main_id,
                ra,
                dec,
                pretype,
                uncmaja,
                uncmina
            FROM NEDTAP.objdir
            WHERE 1 = CONTAINS(
                POINT('ICRS', ra, dec),
                CIRCLE('ICRS', {coordinate.ra}, {coordinate.dec}, {radius_deg})
            )
        """

        rows = self._search_with_retries(adql, context="cone search")
        return [self._row_to_source(row) for row in rows]

    def _query_by_name(self, name: str) -> list[Any]:
        normalized = name.strip()
        if not normalized:
            return []

        try:
            escaped_name = self._escape_adql_string(normalized)
        except ValueError as exc:
            logger.warning("Invalid object name for NED query: %s - %s", name, exc)
            return []
            
        adql = f"""
            SELECT TOP 1
                prefname AS main_id,
                ra,
                dec,
                pretype,
                uncmaja,
                uncmina
            FROM NEDTAP.objdir
            WHERE prefname = '{escaped_name}'
        """

        return self._search_with_retries(adql, context=f"name query for {name}")

    @staticmethod
    def _value(row: Any, keys: list[str], default: Any = None) -> Any:
        """Read first available key from TAP row using common key aliases.
        
        Attempts to access row using bracket notation, then attribute access,
        and returns the first successfully retrieved value.
        """
        for key in keys:
            value = None
            found = False
            try:
                value = row[key]
                found = True
            except (KeyError, TypeError):
                # KeyError: dict-like object doesn't have the key
                # TypeError: object doesn't support item access
                pass

            if not found and hasattr(row, key):
                try:
                    value = getattr(row, key)
                    found = True
                except AttributeError:
                    pass

            if found and value is not None:
                return value
        return default

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        """Convert value to float with a safe default fallback."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _search_with_retries(self, adql: str, context: str) -> list[Any]:
        """Execute TAP query with retry-on-failure behavior."""
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                table = self._service.search(adql)
                return list(table)
            except Exception as exc:
                if attempt == attempts - 1:
                    logger.warning("NED TAP %s failed after retries: %s", context, exc)
                    return []
                time.sleep(self.retry_delay_sec)
        return []

    def _row_to_source(self, row: Any) -> Source:
        main_id = str(self._value(row, ["main_id", "MAIN_ID", "prefname", "PREFNAME"], "UNKNOWN")).strip()
        ra = self._safe_float(self._value(row, ["ra", "RA"], 0.0), 0.0)
        dec = self._safe_float(self._value(row, ["dec", "DEC"], 0.0), 0.0)
        err_maj = self._safe_float(self._value(row, ["uncmaja", "UNCMAJA"], 1.0), 1.0)
        err_min = self._safe_float(self._value(row, ["uncmina", "UNCMINA"], 1.0), 1.0)

        return Source(
            id=f"NED_TAP:{main_id}",
            name=main_id,
            coordinate=Coordinate(
                ra=ra,
                dec=dec,
                pm_ra_mas_per_year=None,
                pm_dec_mas_per_year=None,
            ),
            uncertainty=Uncertainty(ra_error=err_maj, dec_error=err_min),
            photometry=[],
            provenance=Provenance(
                catalog_name="NED",
                catalog_version="tap-live",
                query_timestamp=datetime.utcnow(),
                source_id=main_id,
            ),
        )


class GaiaDR3TapAdapter(CatalogConnector):
    """Live Gaia DR3 adapter via the ESA Gaia Archive TAP service.

    Gaia DR3 does not expose a human-readable name index so ``query_object``
    always returns an empty list.  Use ``cone_search`` with coordinates
    obtained from SIMBAD or NED first.  Results include full astrometry
    (RA, Dec, proper motions, parallax) and G/BP/RP photometry.
    """

    DEFAULT_TAP_URL = "https://gea.esac.esa.int/tap-server/tap"

    def __init__(
        self,
        tap_url: str = DEFAULT_TAP_URL,
        max_records: int = 50,
        tap_service: Optional[TapServiceProtocol] = None,
        request_timeout_sec: float = 15.0,
        max_retries: int = 2,
        retry_delay_sec: float = 0.5,
        max_concurrency: int = 4,
    ):
        self.tap_url = tap_url
        self.max_records = max_records
        self.request_timeout_sec = request_timeout_sec
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self._request_semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._service: TapServiceProtocol

        if tap_service is not None:
            self._service = tap_service
            return

        try:
            import pyvo as _pyvo
        except ImportError as exc:
            raise RuntimeError(
                "GaiaDR3TapAdapter requires pyvo. Install with `pip install -e .[live]`."
            ) from exc

        self._service = _pyvo.dal.TAPService(self.tap_url)

    def query(self, name: str) -> Optional[Source]:
        return None  # Gaia DR3 has no human-readable name index

    async def query_object(self, name: str) -> list[Source]:
        return []  # Use cone_search with coordinates from SIMBAD/NED

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        """Cone search against Gaia DR3 gaiadr3.gaia_source."""
        try:
            return await self._run_io_bound(self._cone_search_sync, coordinate, radius_arcsec)
        except asyncio.TimeoutError:
            logger.warning("Gaia DR3 TAP cone search timed out at RA=%s Dec=%s", coordinate.ra, coordinate.dec)
            return []

    async def _run_io_bound(self, func: Callable[..., _T], *args: Any) -> _T:
        async with self._request_semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args),
                timeout=self.request_timeout_sec,
            )

    def _cone_search_sync(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        if radius_arcsec <= 0:
            return []
        radius_deg = radius_arcsec / 3600.0
        adql = f"""
            SELECT TOP {int(self.max_records)}
                CAST(source_id AS VARCHAR) AS main_id,
                ra, dec, ra_error, dec_error,
                phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag,
                pmra, pmdec, parallax
            FROM gaiadr3.gaia_source
            WHERE 1 = CONTAINS(
                POINT('ICRS', ra, dec),
                CIRCLE('ICRS', {coordinate.ra}, {coordinate.dec}, {radius_deg})
            )
            ORDER BY phot_g_mean_mag
        """
        rows = self._search_with_retries(adql, "Gaia DR3 cone search")
        return [self._row_to_source(row) for row in rows]

    def _search_with_retries(self, adql: str, context: str) -> list[Any]:
        for attempt in range(self.max_retries + 1):
            try:
                return list(self._service.search(adql))
            except Exception as exc:
                if attempt == self.max_retries:
                    logger.warning("Gaia DR3 TAP %s failed after retries: %s", context, exc)
                    return []
                time.sleep(self.retry_delay_sec)
        return []

    @staticmethod
    def _value(row: Any, keys: list[str], default: Any = None) -> Any:
        for key in keys:
            try:
                v = row[key]
                if v is not None:
                    return v
            except (KeyError, TypeError):
                pass
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
        main_id = str(self._value(row, ["main_id", "source_id"], "GAIA_UNKNOWN")).strip()
        ra = self._safe_float(self._value(row, ["ra", "RA"], 0.0), 0.0)
        dec = self._safe_float(self._value(row, ["dec", "DEC"], 0.0), 0.0)
        ra_err = self._safe_float(self._value(row, ["ra_error", "RA_ERROR"], None), 0.3)
        dec_err = self._safe_float(self._value(row, ["dec_error", "DEC_ERROR"], None), 0.3)
        pm_ra = self._value(row, ["pmra", "PMRA"], None)
        pm_dec = self._value(row, ["pmdec", "PMDEC"], None)

        photometry = []
        for band, key in [("G", "phot_g_mean_mag"), ("BP", "phot_bp_mean_mag"), ("RP", "phot_rp_mean_mag")]:
            val = self._value(row, [key, key.upper()], None)
            if val is not None:
                with contextlib.suppress(TypeError, ValueError):
                    photometry.append(Photometry(magnitude=float(val), band=band, magnitude_error=None))

        return Source(
            id=f"GAIA_DR3:{main_id}",
            name=f"Gaia DR3 {main_id}",
            coordinate=Coordinate(
                ra=ra,
                dec=dec,
                pm_ra_mas_per_year=self._safe_float(pm_ra, 0.0) if pm_ra is not None else None,
                pm_dec_mas_per_year=self._safe_float(pm_dec, 0.0) if pm_dec is not None else None,
            ),
            uncertainty=Uncertainty(ra_error=ra_err, dec_error=dec_err),
            photometry=photometry,
            provenance=Provenance(
                catalog_name="GAIA_DR3",
                catalog_version="dr3-tap-live",
                query_timestamp=datetime.utcnow(),
                source_id=main_id,
            ),
        )


class TwoMassTapAdapter(CatalogConnector):
    """Live 2MASS Point Source Catalog adapter via NASA IRSA TAP service.

    Supports cone search returning J/H/Ks photometry.  Name lookup is not
    supported by the IRSA TAP schema — use coordinates from SIMBAD/NED.
    """

    DEFAULT_TAP_URL = "https://irsa.ipac.caltech.edu/TAP"

    def __init__(
        self,
        tap_url: str = DEFAULT_TAP_URL,
        max_records: int = 50,
        tap_service: Optional[TapServiceProtocol] = None,
        request_timeout_sec: float = 15.0,
        max_retries: int = 2,
        retry_delay_sec: float = 0.5,
        max_concurrency: int = 4,
    ):
        self.tap_url = tap_url
        self.max_records = max_records
        self.request_timeout_sec = request_timeout_sec
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self._request_semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._service: TapServiceProtocol

        if tap_service is not None:
            self._service = tap_service
            return

        try:
            import pyvo as _pyvo
        except ImportError as exc:
            raise RuntimeError(
                "TwoMassTapAdapter requires pyvo. Install with `pip install -e .[live]`."
            ) from exc

        self._service = _pyvo.dal.TAPService(self.tap_url)

    def query(self, name: str) -> Optional[Source]:
        return None  # No name index in 2MASS TAP

    async def query_object(self, name: str) -> list[Source]:
        return []  # Use cone_search with position from SIMBAD/NED

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        """Cone search against 2MASS fp_psc."""
        try:
            return await self._run_io_bound(self._cone_search_sync, coordinate, radius_arcsec)
        except asyncio.TimeoutError:
            logger.warning("2MASS TAP cone search timed out at RA=%s Dec=%s", coordinate.ra, coordinate.dec)
            return []

    async def _run_io_bound(self, func: Callable[..., _T], *args: Any) -> _T:
        async with self._request_semaphore:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args),
                timeout=self.request_timeout_sec,
            )

    def _cone_search_sync(self, coordinate: Coordinate, radius_arcsec: float) -> list[Source]:
        if radius_arcsec <= 0:
            return []
        radius_deg = radius_arcsec / 3600.0
        adql = f"""
            SELECT TOP {int(self.max_records)}
                designation AS main_id,
                ra, dec, err_maj, err_min,
                j_m, h_m, k_m
            FROM fp_psc
            WHERE 1 = CONTAINS(
                POINT('J2000', ra, dec),
                CIRCLE('J2000', {coordinate.ra}, {coordinate.dec}, {radius_deg})
            )
            ORDER BY j_m
        """
        rows = self._search_with_retries(adql, "2MASS cone search")
        return [self._row_to_source(row) for row in rows]

    def _search_with_retries(self, adql: str, context: str) -> list[Any]:
        for attempt in range(self.max_retries + 1):
            try:
                return list(self._service.search(adql))
            except Exception as exc:
                if attempt == self.max_retries:
                    logger.warning("2MASS TAP %s failed after retries: %s", context, exc)
                    return []
                time.sleep(self.retry_delay_sec)
        return []

    @staticmethod
    def _value(row: Any, keys: list[str], default: Any = None) -> Any:
        for key in keys:
            try:
                v = row[key]
                if v is not None:
                    return v
            except (KeyError, TypeError):
                pass
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
        main_id = str(self._value(row, ["main_id", "designation", "DESIGNATION"], "2MASS_UNKNOWN")).strip()
        ra = self._safe_float(self._value(row, ["ra", "RA"], 0.0), 0.0)
        dec = self._safe_float(self._value(row, ["dec", "DEC"], 0.0), 0.0)
        err_maj = self._safe_float(self._value(row, ["err_maj", "ERR_MAJ"], None), 1.0)
        err_min = self._safe_float(self._value(row, ["err_min", "ERR_MIN"], None), 1.0)

        photometry = []
        for band, key in [("J", "j_m"), ("H", "h_m"), ("Ks", "k_m")]:
            val = self._value(row, [key, key.upper()], None)
            if val is not None:
                with contextlib.suppress(TypeError, ValueError):
                    photometry.append(Photometry(magnitude=float(val), band=band, magnitude_error=None))

        return Source(
            id=f"2MASS:{main_id}",
            name=main_id,
            coordinate=Coordinate(
                ra=ra,
                dec=dec,
                pm_ra_mas_per_year=None,
                pm_dec_mas_per_year=None,
            ),
            uncertainty=Uncertainty(ra_error=err_maj, dec_error=err_min),
            photometry=photometry,
            provenance=Provenance(
                catalog_name="2MASS",
                catalog_version="psc-tap-live",
                query_timestamp=datetime.utcnow(),
                source_id=main_id,
            ),
        )
