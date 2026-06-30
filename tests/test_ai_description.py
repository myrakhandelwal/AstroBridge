"""Tests for astrobridge.ai_description — LLM-backed object descriptions."""

from datetime import datetime

import pytest

from astrobridge.ai_description import (
    _build_prompt,
    _cache_key,
    _call_stub,
    generate_description,
)
from astrobridge.models import (
    CelestialObject,
    Coordinate,
    ObjectType,
    Photometry,
    Provenance,
    Source,
    Uncertainty,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_object(name: str = "Proxima Centauri", obj_type: ObjectType = ObjectType.STAR) -> CelestialObject:
    return CelestialObject(
        primary_name=name,
        ra=217.429,
        dec=-62.680,
        object_type=obj_type,
        photometry_summary={"V": 11.05, "J": 7.47},
        catalog_entries={},
        source_catalogs=["SIMBAD"],
        alternate_names=["α Cen C"],
    )


def _make_source(name: str = "Proxima Centauri") -> Source:
    return Source(
        id=f"simbad:{name.lower().replace(' ', '-')}",
        name=name,
        coordinate=Coordinate(ra=217.429, dec=-62.680),
        uncertainty=Uncertainty(ra_error=0.1, dec_error=0.1),
        photometry=[Photometry(magnitude=11.05, band="V")],
        provenance=Provenance(
            catalog_name="SIMBAD",
            catalog_version="2024",
            query_timestamp=datetime.utcnow(),
            source_id=name,
        ),
        object_type="star",
    )


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_includes_name():
    obj = _make_object()
    assert "Proxima Centauri" in _build_prompt(obj)


def test_build_prompt_includes_type():
    obj = _make_object(obj_type=ObjectType.GALAXY)
    assert "galaxy" in _build_prompt(obj).lower()


def test_build_prompt_includes_photometry():
    obj = _make_object()
    assert "Photometry" in _build_prompt(obj)


def test_build_prompt_includes_catalogs():
    obj = _make_object()
    assert "SIMBAD" in _build_prompt(obj)


def test_build_prompt_includes_alternate_names():
    obj = _make_object()
    assert "α Cen C" in _build_prompt(obj)


def test_build_prompt_no_photometry():
    obj = CelestialObject(primary_name="Ghost", ra=0.0, dec=0.0)
    prompt = _build_prompt(obj)
    assert "Ghost" in prompt
    assert "Photometry" not in prompt


# ---------------------------------------------------------------------------
# _call_stub
# ---------------------------------------------------------------------------

def test_stub_contains_object_name():
    prompt = _build_prompt(_make_object("M31", ObjectType.GALAXY))
    assert "M31" in _call_stub(prompt, "", "", "", None)


def test_stub_contains_object_type():
    prompt = _build_prompt(_make_object("M31", ObjectType.GALAXY))
    assert "galaxy" in _call_stub(prompt, "", "", "", None).lower()


def test_stub_mentions_ai_provider():
    prompt = _build_prompt(_make_object())
    assert "AI_PROVIDER" in _call_stub(prompt, "", "", "", None)


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------

def test_cache_key_stable():
    obj = _make_object()
    assert _cache_key(obj) == _cache_key(obj)


def test_cache_key_different_objects():
    assert _cache_key(_make_object("M31", ObjectType.GALAXY)) != _cache_key(_make_object("Sirius"))


def test_cache_key_16_chars():
    assert len(_cache_key(_make_object())) == 16


# ---------------------------------------------------------------------------
# generate_description — stub provider
# ---------------------------------------------------------------------------

def test_generate_description_stub_no_conn(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "stub")
    desc = generate_description(_make_object("Sirius"), conn=None)
    assert isinstance(desc, str) and len(desc) > 0


def test_generate_description_falls_back_on_bad_provider(monkeypatch):
    """Unknown provider names fall back to stub without raising."""
    monkeypatch.setenv("AI_PROVIDER", "totally_invalid_provider")
    desc = generate_description(_make_object("M87", ObjectType.GALAXY), conn=None)
    assert isinstance(desc, str) and len(desc) > 0


# ---------------------------------------------------------------------------
# CelestialObject.from_sources round-trip
# ---------------------------------------------------------------------------

def test_celestial_object_from_sources():
    src = _make_source("Proxima Centauri")
    obj = CelestialObject.from_sources([src])
    assert obj.primary_name == "Proxima Centauri"
    assert obj.photometry_summary == {"V": 11.05}
    assert "SIMBAD" in obj.catalog_entries
    assert obj.object_type == ObjectType.STAR


def test_celestial_object_from_sources_empty_raises():
    with pytest.raises(ValueError):
        CelestialObject.from_sources([])


# ---------------------------------------------------------------------------
# CelestialObject.describe()
# ---------------------------------------------------------------------------

def test_describe_star_with_distance():
    obj = CelestialObject(
        primary_name="Proxima Centauri",
        ra=217.429,
        dec=-62.680,
        object_type=ObjectType.STAR,
        parallax_mas=768.5,
        parallax_error_mas=1.3,
        distance_pc=1.30,
        source_catalogs=["Gaia DR3"],
    )
    desc = obj.describe()
    assert "Proxima Centauri" in desc
    assert "star" in desc.lower()
    assert "parsec" in desc.lower()


def test_describe_galaxy_with_redshift():
    obj = CelestialObject(
        primary_name="M31",
        ra=10.68,
        dec=41.27,
        object_type=ObjectType.GALAXY,
        redshift=0.000360,
        redshift_type="spectroscopic",
        source_catalogs=["NED"],
    )
    desc = obj.describe()
    assert "M31" in desc
    assert "galaxy" in desc.lower()
    assert "redshift" in desc.lower()


def test_describe_unknown_object():
    obj = CelestialObject(primary_name="Mystery", ra=0.0, dec=0.0)
    desc = obj.describe()
    assert "Mystery" in desc
