"""Data models for astronomical sources."""
from datetime import datetime
from typing import Optional

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


class MatchResult(BaseModel):
    """Result of a source match."""
    source1_id: str = Field(..., description="First source ID")
    source2_id: str = Field(..., description="Second source ID")
    match_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of match")
    separation_arcsec: float = Field(..., description="Angular separation in arcseconds")
    confidence: float = Field(..., description="Confidence score")


# ---------------------------------------------------------------------------
# Unified dictionary schema  (required by project spec)
# ---------------------------------------------------------------------------

class UnifiedObject(BaseModel):
    """Merged view of an astronomical object across all queried catalogs."""

    primary_name: str
    alternate_names: list = None
    coordinates: dict = None
    catalog_entries: dict = None
    cross_matches: list = None
    ai_description: str = None
    calibrated_image_path: str = None
    object_type: str = None
    photometry_summary: dict = None

    def __init__(self, **data):
        if "alternate_names" not in data:
            data["alternate_names"] = []
        if "catalog_entries" not in data:
            data["catalog_entries"] = {}
        if "cross_matches" not in data:
            data["cross_matches"] = []
        if "photometry_summary" not in data:
            data["photometry_summary"] = {}
        super().__init__(**data)

    @property
    def ra(self) -> float:
        return float((self.coordinates or {}).get("ra", 0.0))

    @property
    def dec(self) -> float:
        return float((self.coordinates or {}).get("dec", 0.0))

    @classmethod
    def from_sources(cls, sources: list, primary_name: str = None) -> "UnifiedObject":
        if not sources:
            raise ValueError("Cannot build UnifiedObject from empty source list")
        ref = sources[0]
        names = []
        photo_merged = {}
        catalog_entries = {}
        for src in sources:
            if src.name not in names:
                names.append(src.name)
            catalog_entries[src.provenance.catalog_name] = {
                "id": src.id, "ra": src.coordinate.ra, "dec": src.coordinate.dec
            }
            for p in (src.photometry or []):
                photo_merged[p.band] = p.magnitude
        chosen = primary_name or names[0]
        return cls(
            primary_name=chosen,
            alternate_names=[n for n in names if n != chosen],
            coordinates={"ra": ref.coordinate.ra, "dec": ref.coordinate.dec, "epoch": "J2000"},
            catalog_entries=catalog_entries,
            photometry_summary=photo_merged,
        )
