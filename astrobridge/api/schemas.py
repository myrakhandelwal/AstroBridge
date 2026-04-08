"""Data schemas for API requests and responses."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


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
    query_type: str = Field(
        ..., 
        description="Type of query: 'name', 'coordinates', or 'natural_language'"
    )
    name: Optional[str] = Field(None, description="Object name for name queries")
    coordinates: Optional[CoordinateRequest] = Field(None, description="Coordinates for cone searches")
    description: Optional[str] = Field(None, description="Natural language description")
    catalogs: Optional[List[str]] = Field(None, description="Specific catalogs to query (optional)")
    auto_route: bool = Field(
        default=True,
        description="Use intelligent routing to select best catalogs"
    )


class SourceResponse(BaseModel):
    """Response with source information."""
    id: str = Field(..., description="Source ID")
    name: str = Field(..., description="Source name")
    ra: float = Field(..., description="Right ascension in degrees")
    dec: float = Field(..., description="Declination in degrees")
    catalog: str = Field(..., description="Catalog source")
    object_type: Optional[str] = Field(None, description="Object type")
    magnitude: Optional[float] = Field(None, description="Magnitude")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "SIMBAD:*2MASS J12345+67890",
                "name": "Proxima Centauri",
                "ra": 217.429,
                "dec": -62.680,
                "catalog": "simbad",
                "object_type": "star",
                "magnitude": 11.05
            }
        }


class MatchResponse(BaseModel):
    """Response with matched sources from multiple catalogs."""
    source1: SourceResponse = Field(..., description="First source")
    source2: SourceResponse = Field(..., description="Second source")
    match_probability: float = Field(..., ge=0, le=1, description="Probability of match")
    separation_arcsec: float = Field(..., ge=0, description="Angular separation in arcseconds")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")


class QueryResponse(BaseModel):
    """Complete response to a query request."""
    query_id: str = Field(..., description="Unique query identifier")
    timestamp: datetime = Field(..., description="Query timestamp")
    status: str = Field(
        ...,
        description="Query status: 'success', 'partial', 'error'"
    )
    query_type: str = Field(..., description="Type of query executed")
    catalogs_queried: List[str] = Field(..., description="Catalogs that were queried")
    sources: List[SourceResponse] = Field(
        ...,
        description="Sources found across all catalogs"
    )
    matches: List[MatchResponse] = Field(
        default=[],
        description="Cross-catalog matches found"
    )
    routing_reasoning: Optional[str] = Field(
        None,
        description="Explanation of catalog routing decision"
    )
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")
    errors: List[str] = Field(default=[], description="Any errors encountered")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "q_550e8400e29b41d4a716446655440000",
                "timestamp": "2026-04-07T14:30:00Z",
                "status": "success",
                "query_type": "name",
                "catalogs_queried": ["simbad", "ned"],
                "sources": [],
                "matches": [],
                "execution_time_ms": 245.5,
                "errors": []
            }
        }
