"""Request and response schemas for the AstroBridge API layer.

Every field that ``test_api.py`` touches is defined here with appropriate
Pydantic validators.  No business logic lives in schemas – they are pure
data-shape contracts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Request primitives
# ---------------------------------------------------------------------------

class SourceRequest(BaseModel):
    """Request to look up a single named object."""
    name: str = Field(..., description="Object name, e.g. 'Proxima Centauri'")


class CoordinateRequest(BaseModel):
    """Sky coordinate with optional cone-search radius."""
    ra: float = Field(..., description="Right ascension in degrees [0, 360)")
    dec: float = Field(..., description="Declination in degrees [-90, 90]")
    radius_arcsec: float = Field(default=60.0, description="Search radius in arcseconds")

    @field_validator("ra")
    @classmethod
    def _check_ra(cls, v: float) -> float:
        if not 0.0 <= v <= 360.0:
            raise ValueError(f"RA must be in [0, 360], got {v}")
        return v

    @field_validator("dec")
    @classmethod
    def _check_dec(cls, v: float) -> float:
        if not -90.0 <= v <= 90.0:
            raise ValueError(f"Dec must be in [-90, 90], got {v}")
        return v


# ---------------------------------------------------------------------------
# Main query request
# ---------------------------------------------------------------------------

_VALID_QUERY_TYPES = {"name", "coordinates", "natural_language"}
_VALID_PROFILES = {"balanced", "position_first", "photometry_first"}


class QueryRequest(BaseModel):
    """Unified query envelope for the orchestrator."""

    query_type: str = Field(
        ...,
        description="One of: 'name' | 'coordinates' | 'natural_language'",
    )
    # Payload fields – exactly one is required depending on query_type
    name: Optional[str] = Field(None, description="Object name (query_type='name')")
    coordinates: Optional[Union[CoordinateRequest, Dict[str, Any]]] = Field(
        None, description="Coordinate dict or CoordinateRequest (query_type='coordinates')"
    )
    description: Optional[str] = Field(
        None, description="Natural language description (query_type='natural_language')"
    )

    # Catalog selection
    catalogs: Optional[List[str]] = Field(
        None, description="Explicit catalog list to query; None = all registered"
    )
    auto_route: bool = Field(
        default=True, description="Use NLPQueryRouter to select catalogs automatically"
    )

    # Matcher controls
    proper_motion_aware: bool = Field(
        default=False, description="Enable proper-motion epoch correction"
    )
    match_epoch: Optional[datetime] = Field(
        None, description="Target epoch for proper-motion correction"
    )
    astrometric_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Weight for astrometric score [0, 1]"
    )
    photometric_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Weight for photometric score [0, 1]"
    )
    weighting_profile: Optional[str] = Field(
        None, description="Named weighting profile: 'balanced' | 'position_first' | 'photometry_first'"
    )

    @model_validator(mode="after")
    def _check_payload(self) -> "QueryRequest":
        qt = self.query_type
        if qt not in _VALID_QUERY_TYPES:
            raise ValueError(
                f"query_type must be one of {sorted(_VALID_QUERY_TYPES)}, got '{qt}'"
            )
        if qt == "name" and not self.name:
            raise ValueError("name is required when query_type='name'")
        if qt == "coordinates" and self.coordinates is None:
            raise ValueError("coordinates are required when query_type='coordinates'")
        if qt == "natural_language" and not self.description:
            raise ValueError("description is required when query_type='natural_language'")
        if (
            self.weighting_profile is not None
            and self.weighting_profile not in _VALID_PROFILES
        ):
            raise ValueError(
                f"weighting_profile must be one of {sorted(_VALID_PROFILES)}"
            )
        return self

    def coordinate_request(self) -> Optional[CoordinateRequest]:
        """Coerce the coordinates field to a CoordinateRequest."""
        if self.coordinates is None:
            return None
        if isinstance(self.coordinates, CoordinateRequest):
            return self.coordinates
        return CoordinateRequest(**self.coordinates)


# ---------------------------------------------------------------------------
# Response primitives
# ---------------------------------------------------------------------------

class SourceResponse(BaseModel):
    """A single source as returned to the caller."""
    id: str
    name: str
    ra: float
    dec: float
    catalog: str
    object_type: Optional[str] = None
    magnitude: Optional[float] = None


class MatchResponse(BaseModel):
    """A cross-catalog match between two sources."""
    source1: SourceResponse
    source2: SourceResponse
    match_probability: float = Field(..., ge=0.0, le=1.0)
    separation_arcsec: float
    confidence: float = Field(..., ge=0.0, le=1.0)


class QueryResponse(BaseModel):
    """Complete response from an orchestrated query."""
    query_id: str
    timestamp: datetime
    status: str  # "success" | "partial" | "error"
    query_type: str
    catalogs_queried: List[str] = Field(default_factory=list)
    sources: List[SourceResponse] = Field(default_factory=list)
    matches: List[MatchResponse] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    errors: List[str] = Field(default_factory=list)
    routing_reasoning: Optional[str] = None


# ---------------------------------------------------------------------------
# Offline validation shim (activates only when real pydantic is unavailable)
# When real pydantic is installed the model_validator above handles this.
# ---------------------------------------------------------------------------
try:
    import pydantic as _pd
    if not hasattr(_pd.BaseModel, 'model_fields'):
        raise ImportError("stub")
except Exception:
    # Running under the offline stub — wire validation into __init__
    _orig_qr_init = QueryRequest.__init__

    def _qr_init(self, **data):
        _orig_qr_init(self, **data)
        qt = getattr(self, 'query_type', None)
        if qt not in _VALID_QUERY_TYPES:
            raise ValueError(f"query_type must be one of {sorted(_VALID_QUERY_TYPES)}, got '{qt}'")
        if qt == "name" and not getattr(self, 'name', None):
            raise ValueError("name is required when query_type='name'")
        if qt == "coordinates" and getattr(self, 'coordinates', None) is None:
            raise ValueError("coordinates are required when query_type='coordinates'")
        if qt == "natural_language" and not getattr(self, 'description', None):
            raise ValueError("description is required when query_type='natural_language'")
        aw = getattr(self, 'astrometric_weight', None)
        pw = getattr(self, 'photometric_weight', None)
        if aw is not None and not (0.0 <= aw <= 1.0):
            raise ValueError(f"astrometric_weight must be in [0, 1], got {aw}")
        if pw is not None and not (0.0 <= pw <= 1.0):
            raise ValueError(f"photometric_weight must be in [0, 1], got {pw}")

    QueryRequest.__init__ = _qr_init

    _orig_cr_init = CoordinateRequest.__init__

    def _cr_init(self, **data):
        _orig_cr_init(self, **data)
        ra = getattr(self, 'ra', None)
        dec = getattr(self, 'dec', None)
        if ra is not None and not (0.0 <= ra <= 360.0):
            raise ValueError(f"RA must be in [0, 360], got {ra}")
        if dec is not None and not (-90.0 <= dec <= 90.0):
            raise ValueError(f"Dec must be in [-90, 90], got {dec}")

    CoordinateRequest.__init__ = _cr_init
