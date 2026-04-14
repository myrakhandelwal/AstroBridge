"""AstroBridge web application.

Endpoints exercised by test_web.py
-----------------------------------
POST /api/identify              – identify an object by free text
GET  /                          – HTML console page
POST /api/jobs                  – submit a background query job
GET  /api/jobs/{job_id}         – poll job status
GET  /api/jobs/{job_id}/result  – retrieve job result
POST /api/analytics/event       – record an analytics event
GET  /api/analytics/summary     – retrieve analytics summary
POST /api/benchmark/run         – run a benchmark
"""
from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from astrobridge.analytics import AnalyticsEvent, AnalyticsStore
from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.benchmarking import BenchmarkRunner
from astrobridge.connectors import NEDConnector, SimbadConnector
from astrobridge.identify import identify_object
from astrobridge.jobs import JobManager
from astrobridge.matching import BayesianMatcher
from astrobridge.routing import NLPQueryRouter

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

class IdentifyRequest(BaseModel):
    input_text: str = Field(..., description="Free-text object query")

class JobSubmitRequest(BaseModel):
    query_type: str = "name"
    name: Optional[str] = None
    description: Optional[str] = None
    coordinates: Optional[dict[str, Any]] = None
    auto_route: bool = True

class BenchmarkRequest(BaseModel):
    iterations: int = Field(default=5, ge=1, le=100)


def _build_app() -> FastAPI:
    _app = FastAPI(title="AstroBridge Web Console", version="0.3.0")

    # Shared singletons – one per process, no thread-safety issues because
    # FastAPI runs handlers in async context.
    _db_path: Optional[str] = os.getenv("ASTROBRIDGE_STATE_DB")

    _orchestrator = AstroBridgeOrchestrator(
        router=NLPQueryRouter(),
        matcher=BayesianMatcher(confidence_threshold=0.01),
        connectors={
            "simbad": SimbadConnector(),
            "ned": NEDConnector(),
        },
    )
    _job_manager = JobManager(db_path=_db_path)
    _analytics = AnalyticsStore(db_path=_db_path)
    _benchmark = BenchmarkRunner(_orchestrator)

    # ------------------------------------------------------------------
    # HTML page
    # ------------------------------------------------------------------

    @_app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _HTML_CONSOLE

    # ------------------------------------------------------------------
    # Identify endpoint
    # ------------------------------------------------------------------



    @_app.post("/api/identify")
    async def identify(req: IdentifyRequest) -> dict[str, Any]:
        if not req.input_text.strip():
            raise HTTPException(status_code=400, detail="input_text must not be empty")

        result = identify_object(req.input_text)

        return {
            "status": "success",
            "object_class": result.object_class.value,
            "top_catalogs": result.top_catalogs,
            "search_radius_arcsec": result.search_radius_arcsec,
            "description": result.description,
            "reasoning": result.reasoning,
        }

    # ------------------------------------------------------------------
    # Jobs endpoints
    # ------------------------------------------------------------------



    @_app.post("/api/jobs")
    async def submit_job(req: JobSubmitRequest) -> dict[str, Any]:
        query_req = QueryRequest(
            query_type=req.query_type,
            name=req.name,
            description=req.description,
            coordinates=req.coordinates,
            auto_route=req.auto_route,
        )
        job_id = await _job_manager.submit_query(query_req, _orchestrator)
        return {"job_id": job_id, "status": "queued"}

    @_app.get("/api/jobs/{job_id}")
    async def get_job_status(job_id: str) -> dict[str, Any]:
        record = _job_manager.get_job(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return record.model_dump(mode="json")

    @_app.get("/api/jobs/{job_id}/result")
    async def get_job_result(job_id: str) -> dict[str, Any]:
        record = _job_manager.get_job(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if record.status not in ("completed", "failed"):
            raise HTTPException(status_code=202, detail="Job not finished yet")
        result = record.result or {}
        return result

    # ------------------------------------------------------------------
    # Analytics endpoints
    # ------------------------------------------------------------------

    @_app.post("/api/analytics/event")
    async def record_event(event: AnalyticsEvent) -> dict[str, Any]:
        _analytics.record(event)
        return {"status": "ok"}

    @_app.get("/api/analytics/summary")
    async def analytics_summary() -> dict[str, Any]:
        return _analytics.summary()

    # ------------------------------------------------------------------
    # Benchmark endpoint
    # ------------------------------------------------------------------



    @_app.post("/api/benchmark/run")
    async def run_benchmark(req: BenchmarkRequest) -> dict[str, Any]:
        from astrobridge.benchmarking import BenchmarkConfig
        config = BenchmarkConfig(iterations=req.iterations)
        result = await _benchmark.run(config)
        return result

    return _app


app = _build_app()


def main() -> None:  # pragma: no cover
    import uvicorn
    uvicorn.run("astrobridge.web.app:app", host="0.0.0.0", port=8000, reload=True)


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_CONSOLE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AstroBridge Web Console</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; }
    h1 { color: #1a1a2e; } h2 { color: #16213e; }
    input, textarea { width: 100%; padding: 8px; margin: 4px 0 12px; box-sizing: border-box; }
    button { background: #0f3460; color: #fff; border: none; padding: 10px 24px; cursor: pointer; }
    button:hover { background: #16213e; }
    pre { background: #f4f4f4; padding: 12px; border-radius: 4px; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>AstroBridge Web Console</h1>

  <h2>Object Identification</h2>
  <label>Object name or description:</label>
  <input id="identify-input" type="text" placeholder="e.g. M31, Proxima Centauri, red dwarf stars">
  <button onclick="runIdentify()">Identify</button>
  <pre id="identify-output">Results will appear here...</pre>

  <h2>Query Engine</h2>
  <label>Object name:</label>
  <input id="query-input" type="text" placeholder="e.g. Proxima Centauri">
  <button onclick="submitJob()">Submit Job</button>
  <pre id="job-output">Job results will appear here...</pre>

  <script>
    async function runIdentify() {
      const text = document.getElementById('identify-input').value;
      const resp = await fetch('/api/identify', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({input_text: text})
      });
      document.getElementById('identify-output').textContent =
        JSON.stringify(await resp.json(), null, 2);
    }

    async function submitJob() {
      const name = document.getElementById('query-input').value;
      const sub = await fetch('/api/jobs', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({query_type: 'name', name: name, auto_route: true})
      });
      const {job_id} = await sub.json();
      document.getElementById('job-output').textContent = 'Job submitted: ' + job_id;

      for (let i = 0; i < 20; i++) {
        await new Promise(r => setTimeout(r, 300));
        const st = await fetch('/api/jobs/' + job_id);
        const data = await st.json();
        if (data.status === 'completed') {
          const res = await fetch('/api/jobs/' + job_id + '/result');
          document.getElementById('job-output').textContent =
            JSON.stringify(await res.json(), null, 2);
          return;
        }
      }
      document.getElementById('job-output').textContent = 'Job ' + job_id + ' still running.';
    }
  </script>
</body>
</html>
"""
