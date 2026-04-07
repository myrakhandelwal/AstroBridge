"""Data models for astronomical sources."""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    """Celestial coordinate."""
    ra: float = Field(..., description="Right ascension in degrees")
    dec: float = Field(..., description="Declination in degrees")
    

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
    photometry: List[Photometry] = Field(default_factory=list, description="Photometric data")
    provenance: Provenance = Field(..., description="Source provenance")


class MatchResult(BaseModel):
    """Result of a source match."""
    source1_id: str = Field(..., description="First source ID")
    source2_id: str = Field(..., description="Second source ID")
    match_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of match")
    separation_arcsec: float = Field(..., description="Angular separation in arcseconds")
    confidence: float = Field(..., description="Confidence score")
