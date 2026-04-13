"""Tests for astrobridge.ai_description — LLM-backed object descriptions."""
import sqlite3

import pytest

from astrobridge.ai_description import (
    _BACKENDS,
    _build_prompt,
    _cache_key,
    _call_stub,
    generate_description,
)
from astrobridge.database import init_db, upsert_object
from astrobridge.models import (
    Coordinate,
    Photometry,
    Provenance,
    Source,
    UnifiedObject,
)
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unified(name: str = "Proxima Centauri", obj_type: str = "star") -> UnifiedObject:
    return UnifiedObject(
        primary_name=name,
        ra=217.429,
        dec=-62.680,
        object_type=obj_type,
        photometry_summary={"V": 11.05, "J": 7.47},
        catalog_entries={"SIMBAD": {"id": "prox-cen", "ra": 217.429, "dec": -62.680}},
        alternate_names=["α Cen C"],
    )


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_includes_name():
    obj = _make_unified()
    prompt = _build_prompt(obj)
    assert "Proxima Centauri" in prompt


def test_build_prompt_includes_type():
    obj = _make_unified(obj_type="galaxy")
    prompt = _build_prompt(obj)
    assert "galaxy" in prompt


def test_build_prompt_includes_photometry():
    obj = _make_unified()
    prompt = _build_prompt(obj)
    assert "Photometry" in prompt


def test_build_prompt_includes_catalogs():
    obj = _make_unified()
    prompt = _build_prompt(obj)
    assert "SIMBAD" in prompt


def test_build_prompt_includes_alternate_names():
    obj = _make_unified()
    prompt = _build_prompt(obj)
    assert "α Cen C" in prompt


def test_build_prompt_no_photometry():
    obj = UnifiedObject(primary_name="Ghost", ra=0.0, dec=0.0)
    prompt = _build_prompt(obj)
    assert "Ghost" in prompt
    assert "Photometry" not in prompt


# ---------------------------------------------------------------------------
# _call_stub
# ---------------------------------------------------------------------------

def test_stub_contains_object_name():
    obj = _make_unified("M31", "galaxy")
    prompt = _build_prompt(obj)
    result = _call_stub(prompt, "", "", "", None)
    assert "M31" in result


def test_stub_contains_object_type():
    obj = _make_unified("M31", "galaxy")
    prompt = _build_prompt(obj)
    result = _call_stub(prompt, "", "", "", None)
    assert "galaxy" in result


def test_stub_mentions_ai_provider():
    obj = _make_unified()
    prompt = _build_prompt(obj)
    result = _call_stub(prompt, "", "", "", None)
    assert "AI_PROVIDER" in result


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------

def test_cache_key_stable():
    obj = _make_unified()
    assert _cache_key(obj) == _cache_key(obj)


def test_cache_key_different_objects():
    a = _make_unified("M31", "galaxy")
    b = _make_unified("Sirius", "star")
    assert _cache_key(a) != _cache_key(b)


def test_cache_key_16_chars():
    obj = _make_unified()
    assert len(_cache_key(obj)) == 16


# ---------------------------------------------------------------------------
# generate_description — stub provider
# ---------------------------------------------------------------------------

def test_generate_description_stub_no_conn(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "stub")
    obj = _make_unified("Sirius", "star")
    desc = generate_description(obj, conn=None)
    assert isinstance(desc, str)
    assert len(desc) > 0


def test_generate_description_stub_with_conn(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "stub")
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    obj = _make_unified("Vega", "star")
    desc = generate_description(obj, conn=conn)
    assert isinstance(desc, str)
    conn.close()


def test_generate_description_force_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "stub")
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    obj = _make_unified()
    # First call
    d1 = generate_description(obj, conn=conn)
    # Force-refresh: should still return a string
    d2 = generate_description(obj, conn=conn, force_refresh=True)
    assert isinstance(d2, str)
    conn.close()


def test_generate_description_falls_back_on_bad_provider(monkeypatch):
    """Unknown provider names fall back to stub without raising."""
    monkeypatch.setenv("AI_PROVIDER", "totally_invalid_provider")
    obj = _make_unified("M87", "galaxy")
    desc = generate_description(obj, conn=None)
    assert isinstance(desc, str)
    assert len(desc) > 0


# ---------------------------------------------------------------------------
# UnifiedObject.from_sources round-trip
# ---------------------------------------------------------------------------

def test_unified_object_from_sources():
    src = Source(
        id="simbad:prox-cen",
        name="Proxima Centauri",
        coordinate=Coordinate(ra=217.429, dec=-62.680),
        uncertainty=__import__("astrobridge.models", fromlist=["Uncertainty"]).Uncertainty(
            ra_error=0.1, dec_error=0.1
        ),
        photometry=[Photometry(magnitude=11.05, band="V")],
        provenance=Provenance(
            catalog_name="SIMBAD",
            catalog_version="2024",
            query_timestamp=datetime.utcnow(),
            source_id="Prox Cen",
        ),
    )
    obj = UnifiedObject.from_sources([src])
    assert obj.primary_name == "Proxima Centauri"
    assert obj.photometry_summary == {"V": 11.05}
    assert obj.catalog_entries is not None
    assert "SIMBAD" in obj.catalog_entries


def test_unified_object_from_sources_empty_raises():
    with pytest.raises(ValueError):
        UnifiedObject.from_sources([])
