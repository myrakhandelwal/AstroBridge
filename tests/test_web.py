"""Tests for the AstroBridge web frontend endpoints."""

import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault(
    "ASTROBRIDGE_STATE_DB",
    str(Path(__file__).resolve().parent / "tmp_web_state.db"),
)

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


def test_submit_job_and_fetch_result():
    submit = client.post(
        "/api/jobs",
        json={
            "query_type": "name",
            "name": "Proxima Centauri",
            "auto_route": True,
        },
    )
    assert submit.status_code == 200
    job_id = submit.json()["job_id"]

    # Poll briefly for completion in background task.
    for _ in range(20):
        status = client.get(f"/api/jobs/{job_id}")
        assert status.status_code == 200
        payload = status.json()
        if payload["status"] == "completed":
            break
        time.sleep(0.05)

    result = client.get(f"/api/jobs/{job_id}/result")
    assert result.status_code == 200
    body = result.json()
    assert body["query_type"] == "name"


def test_analytics_summary_endpoint():
    rec = client.post(
        "/api/analytics/event",
        json={
            "event_type": "education_interaction",
            "query_type": "identify",
            "user_level": "beginner",
            "success": True,
            "latency_ms": 12.5,
        },
    )
    assert rec.status_code == 200

    summary = client.get("/api/analytics/summary")
    assert summary.status_code == 200
    data = summary.json()
    assert data["total_events"] >= 1
    assert "event_type_counts" in data


def test_benchmark_endpoint_runs():
    response = client.post("/api/benchmark/run", json={"iterations": 3})
    assert response.status_code == 200

    data = response.json()
    assert data["iterations"] == 3
    assert "success_rate" in data
    assert "latency_ms" in data
