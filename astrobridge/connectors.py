"""External catalog connectors."""
from datetime import datetime
from typing import List, Optional
from abc import ABC, abstractmethod
from .models import Coordinate, Photometry, Provenance, Source, Uncertainty


class CatalogConnector(ABC):
    """Base class for catalog connectors."""
    
    @abstractmethod
    def query(self, name: str) -> Optional[Source]:
        """Query catalog for a source."""
        pass

    async def query_object(self, name: str) -> List[Source]:
        """Async-compatible object lookup used by integration paths."""
        result = self.query(name)
        return [result] if result is not None else []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> List[Source]:
        """Async-compatible cone search placeholder for future live catalog queries."""
        return []

    @staticmethod
    def _normalized_name(name: str) -> str:
        """Normalize object names for robust matching."""
        return "".join(ch.lower() for ch in name if ch.isalnum())

    @staticmethod
    def _distance_arcsec(coord1: Coordinate, coord2: Coordinate) -> float:
        """Compute simple angular separation in arcseconds."""
        d_ra = coord1.ra - coord2.ra
        d_dec = coord1.dec - coord2.dec
        return ((d_ra * d_ra + d_dec * d_dec) ** 0.5) * 3600.0


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
    """Create a deterministic Source object for local connector datasets."""
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


class SimbadConnector(CatalogConnector):
    """SIMBAD catalog connector."""

    def __init__(self):
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

    async def query_object(self, name: str) -> List[Source]:
        """Return SIMBAD sources for an object query."""
        result = self.query(name)
        return [result] if result is not None else []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> List[Source]:
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

    def __init__(self):
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

    async def query_object(self, name: str) -> List[Source]:
        """Return NED sources for an object query."""
        result = self.query(name)
        return [result] if result is not None else []

    async def cone_search(self, coordinate: Coordinate, radius_arcsec: float) -> List[Source]:
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
