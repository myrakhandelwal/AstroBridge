"""Tests for the AstroBridge web frontend endpoints."""

from fastapi.testclient import TestClient

from astrobridge.web.app import app


client = TestClient(app)


def test_identify_endpoint_success():
    response = client.post("/api/identify", json={"input_text": "M31"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["object_class"] == "galaxy"
    assert data["top_catalogs"][0] == "NED"
    assert "Andromeda" in data["description"]


def test_identify_endpoint_rejects_blank_input():
    response = client.post("/api/identify", json={"input_text": "   "})

    assert response.status_code == 400
    data = response.json()
    assert "input_text must not be empty" in data["detail"]


def test_query_and_identify_pages_load():
    home = client.get("/")

    assert home.status_code == 200
    assert "AstroBridge Web Console" in home.text
    assert "Object Identification" in home.text
