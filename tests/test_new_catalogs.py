"""Tests for new catalog types, routing scores, and TAP adapters."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from astrobridge.connectors import GaiaDR3TapAdapter, TwoMassTapAdapter
from astrobridge.models import Coordinate
from astrobridge.routing.base import CatalogType, ObjectClass
from astrobridge.routing.intelligent import CatalogRanker, NLPQueryRouter
from tests.tap_fakes import StaticTapService

# ---------------------------------------------------------------------------
# CatalogType enum — all new values present
# ---------------------------------------------------------------------------

def test_new_catalog_types_exist():
    assert CatalogType.TWOMASS == "twomass"
    assert CatalogType.HIPPARCOS == "hipparcos"
    assert CatalogType.ALLWISE == "allwise"
    assert CatalogType.EXOPLANET_ARCHIVE == "exoplanet_archive"
    assert CatalogType.VIZIER == "vizier"


def test_catalog_count_at_least_13():
    assert len(CatalogType) >= 13


# ---------------------------------------------------------------------------
# CatalogRanker — new catalog scores present for all object types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("obj_class", list(ObjectClass))
def test_ranking_covers_twomass(obj_class):
    ranked = CatalogRanker.rank_for_class(obj_class, {})
    catalogs = [c for c, _ in ranked]
    assert CatalogType.TWOMASS in catalogs, f"TWOMASS missing for {obj_class}"


@pytest.mark.parametrize("obj_class", list(ObjectClass))
def test_ranking_covers_allwise(obj_class):
    ranked = CatalogRanker.rank_for_class(obj_class, {})
    catalogs = [c for c, _ in ranked]
    assert CatalogType.ALLWISE in catalogs, f"ALLWISE missing for {obj_class}"


def test_gaia_top_ranked_for_stars():
    ranked = CatalogRanker.rank_for_class(ObjectClass.STAR, {})
    top3 = [c for c, _ in ranked[:3]]
    assert CatalogType.GAIA in top3


def test_twomass_boosted_by_nir_property():
    without = dict(CatalogRanker.rank_for_class(ObjectClass.STAR, {}))
    with_nir = dict(CatalogRanker.rank_for_class(ObjectClass.STAR, {"nir": True}))
    assert with_nir[CatalogType.TWOMASS] > without[CatalogType.TWOMASS]


def test_exoplanet_archive_boosted_by_exoplanet_property():
    without = dict(CatalogRanker.rank_for_class(ObjectClass.STAR, {}))
    with_ep = dict(CatalogRanker.rank_for_class(ObjectClass.STAR, {"exoplanet": True}))
    assert with_ep[CatalogType.EXOPLANET_ARCHIVE] > without[CatalogType.EXOPLANET_ARCHIVE]


def test_atlas_top_for_supernovae():
    ranked = dict(CatalogRanker.rank_for_class(ObjectClass.SNE, {}))
    assert ranked[CatalogType.ATLAS] >= 0.75


# ---------------------------------------------------------------------------
# NLP property extraction — new keywords
# ---------------------------------------------------------------------------

def test_nir_keyword_extraction():
    router = NLPQueryRouter()
    props = router._extract_properties("find 2MASS sources in J-band")
    assert props.get("nir") is True


def test_exoplanet_keyword_extraction():
    router = NLPQueryRouter()
    props = router._extract_properties("TESS exoplanet host stars")
    assert props.get("exoplanet") is True


# ---------------------------------------------------------------------------
# GaiaDR3TapAdapter
# ---------------------------------------------------------------------------

GAIA_ROWS = [
    {
        "main_id": "12345678901234567",
        "ra": 217.429,
        "dec": -62.680,
        "ra_error": 0.02,
        "dec_error": 0.02,
        "phot_g_mean_mag": 11.13,
        "phot_bp_mean_mag": 13.02,
        "phot_rp_mean_mag": 9.55,
        "pmra": -3775.4,
        "pmdec": 765.5,
        "parallax": 768.5,
    }
]


@pytest.fixture()
def gaia_adapter():
    return GaiaDR3TapAdapter(tap_service=StaticTapService(GAIA_ROWS))


def test_gaia_query_object_returns_empty(gaia_adapter):
    result = asyncio.get_event_loop().run_until_complete(
        gaia_adapter.query_object("Proxima Centauri")
    )
    assert result == []


def test_gaia_cone_search_returns_sources(gaia_adapter):
    coord = Coordinate(ra=217.429, dec=-62.680)
    result = asyncio.get_event_loop().run_until_complete(
        gaia_adapter.cone_search(coord, radius_arcsec=30)
    )
    assert len(result) == 1
    src = result[0]
    assert src.provenance.catalog_name == "GAIA_DR3"
    assert src.id.startswith("GAIA_DR3:")


def test_gaia_cone_search_includes_proper_motion(gaia_adapter):
    coord = Coordinate(ra=217.429, dec=-62.680)
    result = asyncio.get_event_loop().run_until_complete(
        gaia_adapter.cone_search(coord, radius_arcsec=30)
    )
    src = result[0]
    assert src.coordinate.pm_ra_mas_per_year == pytest.approx(-3775.4)
    assert src.coordinate.pm_dec_mas_per_year == pytest.approx(765.5)


def test_gaia_cone_search_includes_gbrp_photometry(gaia_adapter):
    coord = Coordinate(ra=217.429, dec=-62.680)
    result = asyncio.get_event_loop().run_until_complete(
        gaia_adapter.cone_search(coord, radius_arcsec=30)
    )
    bands = {p.band for p in result[0].photometry}
    assert "G" in bands
    assert "BP" in bands
    assert "RP" in bands


def test_gaia_cone_search_zero_radius_returns_empty(gaia_adapter):
    coord = Coordinate(ra=0.0, dec=0.0)
    result = asyncio.get_event_loop().run_until_complete(
        gaia_adapter.cone_search(coord, radius_arcsec=0)
    )
    assert result == []


def test_gaia_tap_error_returns_empty():
    bad_service = StaticTapService([])
    bad_service.search = MagicMock(side_effect=RuntimeError("TAP error"))
    adapter = GaiaDR3TapAdapter(tap_service=bad_service, max_retries=0)
    coord = Coordinate(ra=0.0, dec=0.0)
    result = asyncio.get_event_loop().run_until_complete(
        adapter.cone_search(coord, radius_arcsec=30)
    )
    assert result == []


def test_gaia_requires_pyvo_when_no_service(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pyvo", None)
    with pytest.raises(RuntimeError, match="pyvo"):
        GaiaDR3TapAdapter()


# ---------------------------------------------------------------------------
# TwoMassTapAdapter
# ---------------------------------------------------------------------------

TWOMASS_ROWS = [
    {
        "main_id": "16572029-2601548",
        "ra": 254.335,
        "dec": -26.032,
        "err_maj": 0.06,
        "err_min": 0.06,
        "j_m": 5.72,
        "h_m": 5.20,
        "k_m": 5.07,
    }
]


@pytest.fixture()
def twomass_adapter():
    return TwoMassTapAdapter(tap_service=StaticTapService(TWOMASS_ROWS))


def test_twomass_query_object_returns_empty(twomass_adapter):
    result = asyncio.get_event_loop().run_until_complete(
        twomass_adapter.query_object("Antares")
    )
    assert result == []


def test_twomass_cone_search_returns_sources(twomass_adapter):
    coord = Coordinate(ra=254.335, dec=-26.032)
    result = asyncio.get_event_loop().run_until_complete(
        twomass_adapter.cone_search(coord, radius_arcsec=30)
    )
    assert len(result) == 1
    src = result[0]
    assert src.provenance.catalog_name == "2MASS"
    assert src.id.startswith("2MASS:")


def test_twomass_cone_search_jhks_photometry(twomass_adapter):
    coord = Coordinate(ra=254.335, dec=-26.032)
    result = asyncio.get_event_loop().run_until_complete(
        twomass_adapter.cone_search(coord, radius_arcsec=30)
    )
    bands = {p.band for p in result[0].photometry}
    assert "J" in bands
    assert "H" in bands
    assert "Ks" in bands


def test_twomass_cone_search_zero_radius(twomass_adapter):
    coord = Coordinate(ra=0.0, dec=0.0)
    result = asyncio.get_event_loop().run_until_complete(
        twomass_adapter.cone_search(coord, radius_arcsec=0)
    )
    assert result == []


def test_twomass_tap_error_returns_empty():
    bad_service = StaticTapService([])
    bad_service.search = MagicMock(side_effect=RuntimeError("IRSA error"))
    adapter = TwoMassTapAdapter(tap_service=bad_service, max_retries=0)
    coord = Coordinate(ra=0.0, dec=0.0)
    result = asyncio.get_event_loop().run_until_complete(
        adapter.cone_search(coord, radius_arcsec=30)
    )
    assert result == []


def test_twomass_requires_pyvo_when_no_service(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pyvo", None)
    with pytest.raises(RuntimeError, match="pyvo"):
        TwoMassTapAdapter()


# ---------------------------------------------------------------------------
# lookup.py — two-step enrichment (offline mode)
# ---------------------------------------------------------------------------

def test_lookup_object_offline_known_object():
    from astrobridge.lookup import lookup_object
    result = asyncio.get_event_loop().run_until_complete(
        lookup_object("Proxima Centauri", live=False)
    )
    assert result is not None
    assert "proxima" in result.primary_name.lower() or result.ra == pytest.approx(217.429, abs=1.0)


def test_lookup_object_offline_unknown_returns_none():
    from astrobridge.lookup import lookup_object
    result = asyncio.get_event_loop().run_until_complete(
        lookup_object("XYZZY_NONEXISTENT_OBJECT_9999", live=False)
    )
    assert result is None


def test_lookup_by_coordinates_offline():
    from astrobridge.lookup import lookup_by_coordinates
    results = asyncio.get_event_loop().run_until_complete(
        lookup_by_coordinates(217.429, -62.680, radius_arcsec=120, live=False)
    )
    assert isinstance(results, list)
