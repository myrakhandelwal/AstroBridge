"""Data schemas for API requests and responses."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceRequest(BaseModel):
    """Request to look up a source by name."""
    name: str = Field(..., description="Object name or designation")
    

class CoordinateRequest(BaseModel):
    """Request to search around coordinates."""
    ra: float = Field(..., ge=0, le=360, description="Right ascension in degrees")
    dec: float = Field(..., ge=-90, le=90, description="Declination in degrees")
    radius_arcsec: float = Field(default=60, gt=0, description="Search radius in arcseconds")


class QueryRequest(BaseModel):
    """Complete query request for multi-catalog source search."""
    query_type: Literal["name", "coordinates", "natural_language"] = Field(
        ..., 
        description="Type of query: 'name', 'coordinates', or 'natural_language'"
    )
    name: Optional[str] = Field(None, description="Object name for name queries")
    coordinates: Optional[CoordinateRequest] = Field(None, description="Coordinates for cone searches")
    description: Optional[str] = Field(None, description="Natural language description")
    catalogs: Optional[list[str]] = Field(None, description="Specific catalogs to query (optional)")
    auto_route: bool = Field(
        default=True,
        description="Use intelligent routing to select best catalogs"
    )
    proper_motion_aware: bool = Field(
        default=False,
        description="Enable proper-motion-aware epoch matching in matcher",
    )
    match_epoch: Optional[datetime] = Field(
        None,
        description="Optional target epoch for matching when proper-motion-aware mode is enabled",
    )
    astrometric_weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional astrometric confidence weighting factor",
    )
    photometric_weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional photometric confidence weighting factor",
    )
    weighting_profile: Optional[Literal["balanced", "position_first", "photometry_first"]] = Field(
        None,
        description="Optional weighting profile: balanced, position_first, or photometry_first",
    )

    @model_validator(mode="after")
    def _validate_query_payload(self) -> "QueryRequest":
        """Enforce required payload fields for each query type."""
        if self.query_type == "name" and not self.name:
            raise ValueError("name is required when query_type='name'")
        if self.query_type == "coordinates" and self.coordinates is None:
            raise ValueError("coordinates are required when query_type='coordinates'")
        if self.query_type == "natural_language" and not self.description:
            raise ValueError("description is required when query_type='natural_language'")
        return self


class SourceResponse(BaseModel):
    """Response with source information."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "SIMBAD:*2MASS J12345+67890",
                "name": "Proxima Centauri",
                "ra": 217.429,
                "dec": -62.680,
                "catalog": "simbad",
                "object_type": "star",
                "magnitude": 11.05,
            }
        }
    )

    id: str = Field(..., description="Source ID")
    name: str = Field(..., description="Source name")
    ra: float = Field(..., description="Right ascension in degrees")
    dec: float = Field(..., description="Declination in degrees")
    catalog: str = Field(..., description="Catalog source")
    object_type: Optional[str] = Field(None, description="Object type")
    magnitude: Optional[float] = Field(None, description="Magnitude")


class MatchResponse(BaseModel):
    """Response with matched sources from multiple catalogs."""
    source1: SourceResponse = Field(..., description="First source")
    source2: SourceResponse = Field(..., description="Second source")
    match_probability: float = Field(..., ge=0, le=1, description="Probability of match")
    separation_arcsec: float = Field(..., ge=0, description="Angular separation in arcseconds")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")


class QueryResponse(BaseModel):
    """Complete response to a query request."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_id": "q_550e8400e29b41d4a716446655440000",
                "timestamp": "2026-04-07T14:30:00Z",
                "status": "success",
                "query_type": "name",
                "catalogs_queried": ["simbad", "ned"],
                "sources": [],
                "matches": [],
                "execution_time_ms": 245.5,
                "errors": [],
            }
        }
    )

    query_id: str = Field(..., description="Unique query identifier")
    timestamp: datetime = Field(..., description="Query timestamp")
    status: str = Field(
        ...,
        description="Query status: 'success', 'partial', 'error'"
    )
    query_type: str = Field(..., description="Type of query executed")
    catalogs_queried: list[str] = Field(..., description="Catalogs that were queried")
    sources: list[SourceResponse] = Field(
        ...,
        description="Sources found across all catalogs"
    )
    matches: list[MatchResponse] = Field(
        default_factory=list,
        description="Cross-catalog matches found"
    )
    routing_reasoning: Optional[str] = Field(
        None,
        description="Explanation of catalog routing decision"
    )
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")
