"""Data models for astronomical sources and unified objects."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ObjectType(str, Enum):
    """Canonical classification of astronomical objects."""
    STAR = "star"
    GALAXY = "galaxy"
    QUASAR = "quasar"
    AGN = "agn"
    NEBULA = "nebula"
    CLUSTER = "cluster"
    SNE = "sne"
    UNKNOWN = "unknown"


class Coordinate(BaseModel):
    """Celestial coordinate with optional proper motion."""
    ra: float = Field(..., description="Right ascension in degrees (ICRS)")
    dec: float = Field(..., description="Declination in degrees (ICRS)")
    pm_ra_mas_per_year: Optional[float] = Field(
        None, description="Proper motion in RA (mas/yr, includes cos(dec) factor)"
    )
    pm_dec_mas_per_year: Optional[float] = Field(
        None, description="Proper motion in Dec (mas/yr)"
    )


class Uncertainty(BaseModel):
    """Positional uncertainty."""
    ra_error: float = Field(..., description="RA uncertainty in arcseconds")
    dec_error: float = Field(..., description="Dec uncertainty in arcseconds")
    ra_dec_correlation: Optional[float] = Field(
        None, description="RA-Dec error correlation coefficient (-1 to 1)"
    )


class Photometry(BaseModel):
    """Single-band photometric measurement."""
    magnitude: float = Field(..., description="Magnitude value")
    band: str = Field(..., description="Filter/band name (e.g. 'G', 'V', 'J')")
    magnitude_error: Optional[float] = Field(None, description="Magnitude uncertainty")


class Provenance(BaseModel):
    """Source provenance — which catalog, when queried."""
    catalog_name: str = Field(..., description="Catalog name (e.g. 'SIMBAD', 'Gaia DR3')")
    catalog_version: str = Field(..., description="Catalog version or release")
    query_timestamp: datetime = Field(..., description="When the source was queried")
    source_id: str = Field(..., description="Catalog-internal source identifier")


class Source(BaseModel):
    """A single astronomical source as returned by one catalog."""
    id: str = Field(..., description="Unique source identifier (catalog:id)")
    name: str = Field(..., description="Source name from catalog")
    coordinate: Coordinate = Field(..., description="Sky position")
    uncertainty: Uncertainty = Field(..., description="Positional uncertainty")
    photometry: list[Photometry] = Field(default_factory=list)
    provenance: Provenance = Field(..., description="Origin catalog and query metadata")
    # Optional fields carried from catalog responses
    object_type: Optional[str] = Field(None, description="Raw classification string from catalog")
    parallax_mas: Optional[float] = Field(None, description="Parallax in milliarcseconds (Gaia)")
    parallax_error_mas: Optional[float] = Field(None, description="Parallax uncertainty (mas)")
    redshift: Optional[float] = Field(None, description="Spectroscopic or photometric redshift")
    redshift_error: Optional[float] = Field(None, description="Redshift uncertainty")
    redshift_type: Optional[str] = Field(None, description="'spectroscopic' | 'photometric'")


# ---------------------------------------------------------------------------
# Catalog priority for field synthesis
# ---------------------------------------------------------------------------

_POSITION_PRIORITY = ["Gaia DR3", "2MASS", "NED", "SIMBAD"]
_PARALLAX_PRIORITY = ["Gaia DR3"]
_REDSHIFT_PRIORITY = ["NED", "SDSS"]
_CLASS_PRIORITY = ["SIMBAD", "NED"]


def _catalog_rank(catalog_name: str, priority_list: list[str]) -> int:
    """Return priority rank (lower = better). Unknown catalogs ranked last."""
    for i, name in enumerate(priority_list):
        if name.lower() in catalog_name.lower():
            return i
    return len(priority_list)


class CelestialObject(BaseModel):
    """
    A synthesized view of one astronomical object, merging data from
    multiple catalogs using best-source-per-field priority rules.

    Researcher access
    -----------------
    ``catalog_entries`` — raw :class:`Source` objects keyed by catalog name.

    Learner access
    --------------
    ``describe()`` — template-driven plain-English summary paragraph.
    """

    # Identity
    primary_name: str = Field(..., description="Canonical display name")
    alternate_names: list[str] = Field(
        default_factory=list, description="All other known names/designations"
    )

    # Classification
    object_type: ObjectType = Field(
        ObjectType.UNKNOWN, description="Canonical object class"
    )
    raw_classification: Optional[str] = Field(
        None, description="Verbatim classification string from best catalog (e.g. 'Em*', 'SyG')"
    )
    classification_source: Optional[str] = Field(
        None, description="Catalog that provided the classification"
    )

    # Position (owned by highest-precision catalog)
    ra: float = Field(..., description="Right ascension in degrees (ICRS)")
    dec: float = Field(..., description="Declination in degrees (ICRS)")
    position_error_arcsec: Optional[float] = Field(
        None, description="Typical positional uncertainty in arcseconds"
    )
    position_epoch: Optional[float] = Field(
        None, description="Epoch of the position (e.g. 2016.0 for Gaia DR3)"
    )
    position_source: Optional[str] = Field(
        None, description="Catalog that owns the position"
    )
    pm_ra_mas_per_year: Optional[float] = Field(None, description="Proper motion RA (mas/yr)")
    pm_dec_mas_per_year: Optional[float] = Field(None, description="Proper motion Dec (mas/yr)")

    # Distance — stellar (from Gaia parallax)
    parallax_mas: Optional[float] = Field(None, description="Parallax in milliarcseconds")
    parallax_error_mas: Optional[float] = Field(None, description="Parallax uncertainty (mas)")
    distance_pc: Optional[float] = Field(
        None,
        description=(
            "Distance in parsecs derived from parallax "
            "(only set when parallax_error/parallax < 0.2)"
        ),
    )

    # Distance — extragalactic (from NED / SDSS)
    redshift: Optional[float] = Field(None, description="Redshift z")
    redshift_error: Optional[float] = Field(None, description="Redshift uncertainty")
    redshift_type: Optional[str] = Field(
        None, description="'spectroscopic' | 'photometric' | 'unknown'"
    )
    redshift_source: Optional[str] = Field(
        None, description="Catalog that provided the redshift"
    )

    # Photometry (best available per band)
    photometry_summary: dict[str, float] = Field(
        default_factory=dict, description="Band → magnitude (best value per band)"
    )

    # Researcher access
    catalog_entries: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw Source objects keyed by catalog name",
    )
    source_catalogs: list[str] = Field(
        default_factory=list, description="Ordered list of contributing catalogs"
    )

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_sources(cls, sources: list[Source]) -> "CelestialObject":
        """
        Build a CelestialObject by synthesizing a cluster of co-located Sources.

        Field ownership rules
        ---------------------
        Position      : Gaia DR3 > 2MASS > NED > SIMBAD
        Parallax      : Gaia DR3 only
        Redshift      : NED > SDSS
        Classification: SIMBAD > NED
        Names         : union across all catalogs
        Photometry    : first catalog per band
        """
        if not sources:
            raise ValueError("Cannot build CelestialObject from empty source list")

        pos_sorted = sorted(sources, key=lambda s: _catalog_rank(s.provenance.catalog_name, _POSITION_PRIORITY))
        cls_sorted = sorted(sources, key=lambda s: _catalog_rank(s.provenance.catalog_name, _CLASS_PRIORITY))

        # ── Position ──────────────────────────────────────────────────────────
        pos_src = pos_sorted[0]
        position_source = pos_src.provenance.catalog_name
        pos_error = (pos_src.uncertainty.ra_error + pos_src.uncertainty.dec_error) / 2.0

        position_epoch: Optional[float] = None
        cn = position_source.lower()
        if "gaia" in cn and "dr3" in cn:
            position_epoch = 2016.0
        elif "gaia" in cn and "dr2" in cn:
            position_epoch = 2015.5

        # ── Classification ────────────────────────────────────────────────────
        raw_classification: Optional[str] = None
        classification_source: Optional[str] = None
        object_type = ObjectType.UNKNOWN

        for src in cls_sorted:
            if src.object_type:
                raw_classification = src.object_type
                classification_source = src.provenance.catalog_name
                object_type = _infer_object_type(src.object_type)
                break

        # ── Parallax / stellar distance (Gaia only) ───────────────────────────
        parallax_mas: Optional[float] = None
        parallax_error_mas: Optional[float] = None
        distance_pc: Optional[float] = None

        for src in sources:
            if "gaia" in src.provenance.catalog_name.lower() and src.parallax_mas is not None:
                parallax_mas = src.parallax_mas
                parallax_error_mas = src.parallax_error_mas
                if parallax_mas > 0:
                    rel_err = (parallax_error_mas or 0.0) / parallax_mas
                    if rel_err < 0.2:
                        distance_pc = 1000.0 / parallax_mas
                break

        # ── Redshift (NED preferred) ───────────────────────────────────────────
        redshift: Optional[float] = None
        redshift_error: Optional[float] = None
        redshift_type: Optional[str] = None
        redshift_source: Optional[str] = None

        rz_candidates = sorted(
            [s for s in sources if s.redshift is not None],
            key=lambda s: _catalog_rank(s.provenance.catalog_name, _REDSHIFT_PRIORITY),
        )
        if rz_candidates:
            rz_src = rz_candidates[0]
            redshift = rz_src.redshift
            redshift_error = rz_src.redshift_error
            redshift_type = rz_src.redshift_type or "unknown"
            redshift_source = rz_src.provenance.catalog_name

        # ── Names ─────────────────────────────────────────────────────────────
        primary_name = cls_sorted[0].name if cls_sorted else sources[0].name
        seen: set[str] = {primary_name}
        alternate_names: list[str] = []
        for src in sources:
            if src.name and src.name not in seen:
                alternate_names.append(src.name)
                seen.add(src.name)

        # ── Photometry (first catalog per band) ────────────────────────────────
        photometry_summary: dict[str, float] = {}
        for src in sources:
            for phot in src.photometry:
                photometry_summary.setdefault(phot.band, phot.magnitude)

        # ── Catalog entries ───────────────────────────────────────────────────
        catalog_entries: dict[str, Any] = {}
        source_catalogs: list[str] = []
        for src in sources:
            cname = src.provenance.catalog_name
            catalog_entries[cname] = src
            if cname not in source_catalogs:
                source_catalogs.append(cname)

        return cls(
            primary_name=primary_name,
            alternate_names=alternate_names,
            object_type=object_type,
            raw_classification=raw_classification,
            classification_source=classification_source,
            ra=pos_src.coordinate.ra,
            dec=pos_src.coordinate.dec,
            position_error_arcsec=pos_error,
            position_epoch=position_epoch,
            position_source=position_source,
            pm_ra_mas_per_year=pos_src.coordinate.pm_ra_mas_per_year,
            pm_dec_mas_per_year=pos_src.coordinate.pm_dec_mas_per_year,
            parallax_mas=parallax_mas,
            parallax_error_mas=parallax_error_mas,
            distance_pc=distance_pc,
            redshift=redshift,
            redshift_error=redshift_error,
            redshift_type=redshift_type,
            redshift_source=redshift_source,
            photometry_summary=photometry_summary,
            catalog_entries=catalog_entries,
            source_catalogs=source_catalogs,
        )

    # ------------------------------------------------------------------ #
    # Learner interface                                                     #
    # ------------------------------------------------------------------ #

    def describe(self) -> str:
        """
        Return a plain-English summary suitable for a student or curious reader.

        Template-based — no LLM required.  For richer AI-generated descriptions,
        call :func:`astrobridge.ai_description.generate_description` with this object.
        """
        parts: list[str] = []

        obj_label = _object_label(self.object_type, self.raw_classification)
        parts.append(f"{self.primary_name} is {obj_label}.")

        if self.distance_pc is not None:
            ly = self.distance_pc * 3.2616
            if ly < 100:
                parts.append(
                    f"It lies {self.distance_pc:.2f} parsecs "
                    f"({ly:.2f} light-years) from Earth."
                )
            else:
                parts.append(f"It lies {self.distance_pc:.0f} parsecs from Earth.")
        elif self.redshift is not None and self.redshift > 0:
            dist_mpc = (self.redshift * 3e5) / 70.0
            parts.append(
                f"It has a redshift of z = {self.redshift:.4f}, "
                f"placing it approximately {dist_mpc:.0f} Mpc from Earth."
            )

        if self.pm_ra_mas_per_year is not None and self.distance_pc is not None:
            pm_total = (
                self.pm_ra_mas_per_year ** 2 + (self.pm_dec_mas_per_year or 0.0) ** 2
            ) ** 0.5
            if pm_total > 500:
                parts.append(
                    f"It has a large proper motion of {pm_total:.0f} mas/yr."
                )

        if self.photometry_summary:
            band_str = ", ".join(
                f"{b}={m:.1f}" for b, m in sorted(self.photometry_summary.items())[:3]
            )
            parts.append(f"Brightness: {band_str} (magnitudes).")

        if self.source_catalogs:
            parts.append(f"Data sourced from {', '.join(self.source_catalogs)}.")

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SIMBAD_TYPE_MAP: dict[str, ObjectType] = {
    "*": ObjectType.STAR, "**": ObjectType.STAR, "V*": ObjectType.STAR,
    "Em*": ObjectType.STAR, "Be*": ObjectType.STAR, "WD*": ObjectType.STAR,
    "MS*": ObjectType.STAR, "RG*": ObjectType.STAR, "SG*": ObjectType.STAR,
    "s*r": ObjectType.STAR, "s*b": ObjectType.STAR, "s*y": ObjectType.STAR,
    "G": ObjectType.GALAXY, "rG": ObjectType.GALAXY, "GiP": ObjectType.GALAXY,
    "SyG": ObjectType.AGN, "Sy1": ObjectType.AGN, "Sy2": ObjectType.AGN,
    "QSO": ObjectType.QUASAR, "AGN": ObjectType.AGN, "Bla": ObjectType.QUASAR,
    "PN": ObjectType.NEBULA, "HII": ObjectType.NEBULA, "SNR": ObjectType.SNE,
    "ISM": ObjectType.NEBULA, "MoC": ObjectType.NEBULA,
    "GlC": ObjectType.CLUSTER, "OpC": ObjectType.CLUSTER, "Cl*": ObjectType.CLUSTER,
    "GrG": ObjectType.CLUSTER, "SN": ObjectType.SNE,
}

_KEYWORD_TYPE_MAP: list[tuple[list[str], ObjectType]] = [
    (["galaxy", "spiral", "elliptical", "lenticular", "irregular"], ObjectType.GALAXY),
    (["quasar", "qso", "blazar", "bll"], ObjectType.QUASAR),
    (["agn", "seyfert", "liner", "active nucleus"], ObjectType.AGN),
    (["nebula", "hii region", "planetary nebula", "supernova remnant"], ObjectType.NEBULA),
    (["cluster", "globular", "open cluster", "association"], ObjectType.CLUSTER),
    (["supernova", "transient", "nova"], ObjectType.SNE),
    (["star", "dwarf", "giant", "binary", "pulsar", "white dwarf"], ObjectType.STAR),
]


def _infer_object_type(raw: str) -> ObjectType:
    """Map a raw catalog classification string to ObjectType."""
    if raw in _SIMBAD_TYPE_MAP:
        return _SIMBAD_TYPE_MAP[raw]
    lower = raw.lower()
    for keywords, otype in _KEYWORD_TYPE_MAP:
        if any(kw in lower for kw in keywords):
            return otype
    return ObjectType.UNKNOWN


def _object_label(otype: ObjectType, raw: Optional[str]) -> str:
    """Return a human-readable indefinite noun phrase for describe()."""
    raw_note = f" ({raw})" if raw and raw != otype.value else ""
    labels: dict[ObjectType, str] = {
        ObjectType.STAR: f"a star{raw_note}",
        ObjectType.GALAXY: f"a galaxy{raw_note}",
        ObjectType.QUASAR: f"a quasar{raw_note}",
        ObjectType.AGN: f"an active galactic nucleus{raw_note}",
        ObjectType.NEBULA: f"a nebula{raw_note}",
        ObjectType.CLUSTER: f"a stellar cluster{raw_note}",
        ObjectType.SNE: f"a supernova or transient{raw_note}",
        ObjectType.UNKNOWN: f"an astronomical object{raw_note}",
    }
    return labels.get(otype, f"an astronomical object{raw_note}")


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------

class MatchResult(BaseModel):
    """Result of a probabilistic cross-match between two sources."""
    source1_id: str = Field(..., description="Reference source ID")
    source2_id: str = Field(..., description="Candidate source ID")
    match_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Bayesian posterior P(match|data)"
    )
    separation_arcsec: float = Field(..., description="Angular separation in arcseconds")
    confidence: float = Field(..., description="Composite confidence score")
