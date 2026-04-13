"""Data models for astronomical sources."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    """Celestial coordinate."""
    ra: float = Field(..., description="Right ascension in degrees")
    dec: float = Field(..., description="Declination in degrees")
    pm_ra_mas_per_year: Optional[float] = Field(
        None,
        description="Proper motion in RA direction (mas/year)",
    )
    pm_dec_mas_per_year: Optional[float] = Field(
        None,
        description="Proper motion in Dec direction (mas/year)",
    )
    

class Uncertainty(BaseModel):
    """Positional uncertainty."""
    ra_error: float = Field(..., description="RA uncertainty in arcseconds")
    dec_error: float = Field(..., description="Dec uncertainty in arcseconds")


class Photometry(BaseModel):
    """Photometric measurement."""
    magnitude: float = Field(..., description="Magnitude value")
    band: str = Field(..., description="Filter band (e.g., 'V', 'J')")
    magnitude_error: Optional[float] = Field(None, description="Magnitude uncertainty")


class Provenance(BaseModel):
    """Source provenance information."""
    catalog_name: str = Field(..., description="Name of the catalog")
    catalog_version: str = Field(..., description="Catalog version")
    query_timestamp: datetime = Field(..., description="When source was queried")
    source_id: str = Field(..., description="Catalog-specific source identifier")


class Source(BaseModel):
    """Astronomical source."""
    id: str = Field(..., description="Unique source identifier")
    name: str = Field(..., description="Source name")
    coordinate: Coordinate = Field(..., description="Position")
    uncertainty: Uncertainty = Field(..., description="Position uncertainty")
    photometry: list[Photometry] = Field(default_factory=list, description="Photometric data")
    provenance: Provenance = Field(..., description="Source provenance")


class UnifiedObject(BaseModel):
    """A merged view of the same astronomical object across multiple catalogs."""

    primary_name: str = Field(..., description="Best-effort display name for the object")
    ra: float = Field(..., description="Right ascension in degrees")
    dec: float = Field(..., description="Declination in degrees")
    object_type: Optional[str] = Field(None, description="Inferred object type string")
    photometry_summary: Optional[dict[str, float]] = Field(
        None, description="Band → magnitude mapping merged across catalogs"
    )
    catalog_entries: Optional[dict[str, Any]] = Field(
        None, description="Catalog name → dict of basic source info"
    )
    alternate_names: list[str] = Field(
        default_factory=list, description="Other names from contributing sources"
    )

    @classmethod
    def from_sources(cls, sources: list["Source"]) -> "UnifiedObject":
        """Build a UnifiedObject by merging a cluster of co-located Sources."""
        if not sources:
            raise ValueError("Cannot build UnifiedObject from empty source list")

        primary = sources[0]
        photometry_summary: dict[str, float] = {}
        catalog_entries: dict[str, Any] = {}
        alternate_names: list[str] = []

        for src in sources:
            for phot in src.photometry:
                photometry_summary.setdefault(phot.band, phot.magnitude)
            catalog_entries[src.provenance.catalog_name] = {
                "id": src.id,
                "ra": src.coordinate.ra,
                "dec": src.coordinate.dec,
            }
            if src.name != primary.name and src.name not in alternate_names:
                alternate_names.append(src.name)

        return cls(
            primary_name=primary.name,
            ra=primary.coordinate.ra,
            dec=primary.coordinate.dec,
            photometry_summary=photometry_summary or None,
            catalog_entries=catalog_entries or None,
            alternate_names=alternate_names,
        )


class MatchResult(BaseModel):
    """Result of a source match."""
    source1_id: str = Field(..., description="First source ID")
    source2_id: str = Field(..., description="Second source ID")
    match_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of match")
    separation_arcsec: float = Field(..., description="Angular separation in arcseconds")
    confidence: float = Field(..., description="Confidence score")
