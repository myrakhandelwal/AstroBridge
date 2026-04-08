"""Unit tests for live TAP adapters using injected fake services."""

import pytest

from astrobridge.connectors import NedTapAdapter, SimbadTapAdapter
from astrobridge.models import Coordinate


class FakeRow(dict):
    """Simple row object matching minimal TAP row behavior."""

    @property
    def colnames(self):
        return list(self.keys())


class FakeTapService:
    """Captures ADQL and returns deterministic rows."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.queries = []

    def search(self, adql):
        self.queries.append(adql)
        if not self.responses:
            return []
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class SlowTapService:
    """Service that sleeps to simulate slow network responses."""

    def __init__(self, delay_sec=0.1):
        self.delay_sec = delay_sec
        self.queries = []

    def search(self, adql):
        import time

        self.queries.append(adql)
        time.sleep(self.delay_sec)
        return []


@pytest.mark.asyncio
async def test_simbad_tap_query_object_maps_row_to_source():
    service = FakeTapService(
        responses=[
            [
                FakeRow(
                    main_id="Proxima Cen",
                    ra=217.429,
                    dec=-62.680,
                    coo_err_maj=0.3,
                    coo_err_min=0.4,
                    flux=11.05,
                )
            ]
        ]
    )
    adapter = SimbadTapAdapter(tap_service=service)

    results = await adapter.query_object("Prox Cen")

    assert len(results) == 1
    source = results[0]
    assert source.id == "SIMBAD_TAP:Proxima Cen"
    assert source.coordinate.ra == 217.429
    assert source.coordinate.dec == -62.68
    assert source.provenance.catalog_name == "SIMBAD"
    assert source.photometry[0].band == "V"
    assert source.photometry[0].magnitude == 11.05


@pytest.mark.asyncio
async def test_simbad_tap_query_escapes_single_quote():
    service = FakeTapService(responses=[[]])
    adapter = SimbadTapAdapter(tap_service=service)

    await adapter.query_object("Barnard's Star")

    assert service.queries
    assert "Barnard''s Star" in service.queries[0]


@pytest.mark.asyncio
async def test_simbad_tap_cone_search_zero_radius_returns_empty():
    service = FakeTapService(responses=[])
    adapter = SimbadTapAdapter(tap_service=service)

    results = await adapter.cone_search(Coordinate(ra=10.0, dec=20.0), 0)

    assert results == []
    assert service.queries == []


@pytest.mark.asyncio
async def test_ned_tap_query_object_maps_row_to_source():
    service = FakeTapService(
        responses=[
            [
                FakeRow(
                    main_id="NGC 5128",
                    ra=201.365,
                    dec=-43.019,
                    pretype="G",
                )
            ]
        ]
    )
    adapter = NedTapAdapter(tap_service=service)

    results = await adapter.query_object("NGC 5128")

    assert len(results) == 1
    source = results[0]
    assert source.id == "NED_TAP:NGC 5128"
    assert source.coordinate.ra == 201.365
    assert source.coordinate.dec == -43.019
    assert source.provenance.catalog_name == "NED"


@pytest.mark.asyncio
async def test_ned_tap_cone_search_builds_circle_query_and_maps_rows():
    service = FakeTapService(
        responses=[
            [
                FakeRow(main_id="ObjA", ra=180.0, dec=45.0, pretype="G"),
                FakeRow(main_id="ObjB", ra=180.01, dec=45.01, pretype="QSO"),
            ]
        ]
    )
    adapter = NedTapAdapter(tap_service=service, max_records=10)

    results = await adapter.cone_search(Coordinate(ra=180.0, dec=45.0), 300)

    assert len(results) == 2
    assert "CIRCLE('ICRS', 180.0, 45.0" in service.queries[0]
    assert "SELECT TOP 10" in service.queries[0]


@pytest.mark.asyncio
async def test_simbad_tap_retries_then_succeeds():
    service = FakeTapService(
        responses=[
            RuntimeError("temporary TAP failure"),
            [
                FakeRow(
                    main_id="Retry Star",
                    ra=123.0,
                    dec=4.5,
                    coo_err_maj=0.4,
                    coo_err_min=0.4,
                    flux=10.0,
                )
            ],
        ]
    )
    adapter = SimbadTapAdapter(tap_service=service, max_retries=1, retry_delay_sec=0.0)

    results = await adapter.query_object("Retry Star")

    assert len(results) == 1
    assert results[0].id == "SIMBAD_TAP:Retry Star"
    assert len(service.queries) == 2


@pytest.mark.asyncio
async def test_ned_tap_retry_exhaustion_returns_empty():
    service = FakeTapService(
        responses=[RuntimeError("fail1"), RuntimeError("fail2"), RuntimeError("fail3")]
    )
    adapter = NedTapAdapter(tap_service=service, max_retries=2, retry_delay_sec=0.0)

    results = await adapter.query_object("Any")

    assert results == []
    assert len(service.queries) == 3


@pytest.mark.asyncio
async def test_simbad_tap_timeout_returns_empty():
    service = SlowTapService(delay_sec=0.05)
    adapter = SimbadTapAdapter(tap_service=service, request_timeout_sec=0.01)

    results = await adapter.query_object("Slow Star")

    assert results == []


@pytest.mark.asyncio
async def test_ned_tap_malformed_numeric_values_fallback_to_defaults():
    service = FakeTapService(
        responses=[[FakeRow(main_id="BrokenRow", ra="not-a-number", dec=None, pretype="G")]]
    )
    adapter = NedTapAdapter(tap_service=service)

    results = await adapter.query_object("BrokenRow")

    assert len(results) == 1
    assert results[0].coordinate.ra == 0.0
    assert results[0].coordinate.dec == 0.0
