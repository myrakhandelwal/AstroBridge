"""Minimal FastAPI frontend for AstroBridge."""

from datetime import datetime

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.matching import BayesianMatcher
from astrobridge.identify import identify_object
from astrobridge.routing import NLPQueryRouter
from astrobridge.routing.base import CatalogType
from astrobridge.models import Source, Coordinate, Uncertainty, Photometry, Provenance


class IdentifyRequest(BaseModel):
  """Request payload for object identification."""

  input_text: str = Field(..., description="Object name or natural-language description")


class WebDemoConnector:
    """Deterministic connector for browser demo queries."""

    def __init__(self, catalog_name: str):
        self.catalog_name = catalog_name

    def query(self, name: str):
        offsets = {
            "simbad": 0.0000,
            "gaia": 0.0005,
            "ned": 0.0010,
            "sdss": -0.0004,
            "wise": 0.0008,
            "panstarrs": -0.0007,
            "ztf": 0.0012,
            "atlas": -0.0011,
        }
        offset = offsets.get(self.catalog_name, 0.0)
        label = name.strip() or "Demo Object"

        return Source(
            id=f"{self.catalog_name}:{label.lower().replace(' ', '_')}",
            name=label,
            coordinate=Coordinate(ra=217.429 + offset, dec=-62.680 + offset),
            uncertainty=Uncertainty(ra_error=0.5, dec_error=0.5),
            photometry=[Photometry(magnitude=11.05 + offset, band="V")],
            provenance=Provenance(
                catalog_name=self.catalog_name.upper(),
                catalog_version="web-demo",
                query_timestamp=datetime.utcnow(),
                source_id=f"{self.catalog_name.upper()}:{label}",
            ),
        )


def build_orchestrator() -> AstroBridgeOrchestrator:
    orchestrator = AstroBridgeOrchestrator(
        router=NLPQueryRouter(),
        matcher=BayesianMatcher(),
    )
    for catalog in CatalogType:
        orchestrator.add_connector(catalog.value, WebDemoConnector(catalog.value))
    return orchestrator


orchestrator = build_orchestrator()
app = FastAPI(title="AstroBridge Web", version="0.1.0")


INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>AstroBridge Web</title>
  <style>
    :root {
      --bg-1: #0f1a1f;
      --bg-2: #1b2a34;
      --card: #f8f5ef;
      --ink: #1a1a1a;
      --accent: #d97a2b;
      --accent-2: #2c9f8f;
      --muted: #5d6570;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background: radial-gradient(1200px 500px at 15% -20%, #2d4858 0%, var(--bg-1) 45%, var(--bg-2) 100%);
      color: #fff;
      min-height: 100vh;
      padding: 24px;
    }
    .wrap { max-width: 1100px; margin: 0 auto; }
    h1 { margin: 0 0 8px 0; font-size: 2.1rem; letter-spacing: 0.4px; }
    .sub { margin: 0 0 18px 0; color: #d2dbe2; }
    .grid { display: grid; grid-template-columns: 1.05fr 1.35fr; gap: 16px; }
    .card {
      background: var(--card);
      color: var(--ink);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 14px 40px rgba(0, 0, 0, 0.24);
    }
    label { display: block; font-size: 0.84rem; margin: 10px 0 6px; color: #333; }
    input, select, textarea {
      width: 100%;
      border: 1px solid #d6d9dd;
      background: #fff;
      border-radius: 10px;
      padding: 10px;
      font-size: 0.95rem;
    }
    textarea { min-height: 92px; resize: vertical; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
    .btns { display: flex; gap: 10px; margin-top: 14px; }
    button {
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      cursor: pointer;
      font-weight: 600;
    }
    .primary { background: var(--accent); color: #fff; }
    .secondary { background: #e5e8ec; color: #1d2935; }
    .pill {
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      background: #edf7f5;
      color: #10695e;
      font-size: 0.78rem;
      margin-right: 6px;
      margin-bottom: 6px;
    }
    .meta { color: var(--muted); font-size: 0.9rem; }
    .split { display: grid; grid-template-columns: 1fr; gap: 12px; }
    .panel {
      border: 1px solid #e8ecef;
      border-radius: 12px;
      padding: 12px;
      background: #fff;
    }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.9rem; }
    th, td { border-bottom: 1px solid #eceff3; text-align: left; padding: 7px 6px; }
    .mono { font-family: ui-monospace, Menlo, Consolas, monospace; }
    .ok { color: #167a6e; font-weight: 700; }
    .warn { color: #9b5a00; font-weight: 700; }
    .err { color: #9f1f2b; font-weight: 700; }
    @media (max-width: 940px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<div class="wrap">
  <h1>AstroBridge Web Console</h1>
  <p class="sub">Run cross-catalog queries with proper-motion and confidence controls in one place.</p>
  <div class="grid">
    <section class="card">
      <h3>Query</h3>
      <label>Query Type</label>
      <select id="queryType">
        <option value="name">name</option>
        <option value="natural_language">natural_language</option>
      </select>

      <label>Name</label>
      <input id="name" value="Proxima Centauri" />

      <label>Description (for natural language)</label>
      <textarea id="description">Find nearby red dwarf stars</textarea>

      <div class="row3">
        <div>
          <label>Proper Motion Aware</label>
          <select id="pmAware">
            <option value="false" selected>false</option>
            <option value="true">true</option>
          </select>
        </div>
        <div>
          <label>Weighting Profile</label>
          <select id="profile">
            <option value="balanced" selected>balanced</option>
            <option value="position_first">position_first</option>
            <option value="photometry_first">photometry_first</option>
          </select>
        </div>
        <div>
          <label>Match Epoch (optional)</label>
          <input id="epoch" placeholder="2020-01-01T00:00:00" />
        </div>
      </div>

      <div class="row">
        <div>
          <label>Astrometric Weight (optional)</label>
          <input id="aw" type="number" step="0.1" min="0" max="1" placeholder="e.g. 0.8" />
        </div>
        <div>
          <label>Photometric Weight (optional)</label>
          <input id="pw" type="number" step="0.1" min="0" max="1" placeholder="e.g. 0.2" />
        </div>
      </div>

      <div class="btns">
        <button class="primary" id="runBtn">Run Query</button>
        <button class="secondary" id="clearBtn">Clear Output</button>
      </div>
    </section>

    <section class="card">
      <h3>Results</h3>
      <div id="status" class="meta">Idle.</div>
      <div id="summary" style="margin-top:8px"></div>
      <div id="catalogs" style="margin-top:10px"></div>
      <div id="sources"></div>
      <div id="errors" style="margin-top:10px"></div>
      <hr style="margin:16px 0;border:none;border-top:1px solid #e8ecef;" />
      <h3>Object Identification</h3>
      <div class="split">
        <div class="panel">
          <label>Identify an object or sky target</label>
          <input id="identifyText" value="M31" placeholder="Try M31, Proxima Centauri, or a natural-language query" />
          <div class="btns">
            <button class="primary" id="identifyBtn">Identify Object</button>
          </div>
        </div>
        <div class="panel">
          <div id="identifyStatus" class="meta">Idle.</div>
          <div id="identifyResult" style="margin-top:8px"></div>
          <div id="identifyErrors" style="margin-top:10px"></div>
        </div>
      </div>
    </section>
  </div>
</div>

<script>
const q = (id) => document.getElementById(id);

function asNum(v) {
  if (v === null || v === undefined || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function setHtml(id, html) { q(id).innerHTML = html; }

async function runQuery() {
  const queryType = q("queryType").value;
  const payload = {
    query_type: queryType,
    auto_route: true,
    proper_motion_aware: q("pmAware").value === "true",
    weighting_profile: q("profile").value,
  };

  if (queryType === "name") payload.name = q("name").value;
  if (queryType === "natural_language") payload.description = q("description").value;

  const epoch = q("epoch").value.trim();
  if (epoch) payload.match_epoch = epoch;

  const aw = asNum(q("aw").value);
  const pw = asNum(q("pw").value);
  if (aw !== undefined) payload.astrometric_weight = aw;
  if (pw !== undefined) payload.photometric_weight = pw;

  setHtml("status", "<span class='warn'>Running query...</span>");
  setHtml("summary", "");
  setHtml("catalogs", "");
  setHtml("sources", "");
  setHtml("errors", "");

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    const statusClass = data.status === "success" ? "ok" : (data.status === "partial" ? "warn" : "err");
    setHtml("status", `<span class='${statusClass}'>${data.status.toUpperCase()}</span> · ${data.execution_time_ms.toFixed(2)} ms`);

    setHtml("summary", `
      <div class="meta mono">query_id: ${data.query_id}</div>
      <div class="meta">sources: <b>${data.sources.length}</b> · matches: <b>${data.matches.length}</b></div>
      <div class="meta">query_type: ${data.query_type}</div>
      ${data.routing_reasoning ? `<div class="meta">routing: ${data.routing_reasoning}</div>` : ""}
    `);

    setHtml("catalogs", data.catalogs_queried.map((c) => `<span class='pill'>${c}</span>`).join(" "));

    if (data.sources.length) {
      const rows = data.sources.map((s) => `
        <tr>
          <td>${s.name}</td>
          <td class='mono'>${s.catalog}</td>
          <td class='mono'>${s.ra.toFixed(5)}, ${s.dec.toFixed(5)}</td>
          <td>${s.magnitude ?? "-"}</td>
        </tr>
      `).join("");
      setHtml("sources", `
        <table>
          <thead><tr><th>Name</th><th>Catalog</th><th>Coordinates</th><th>Mag</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `);
    }

    if (data.errors && data.errors.length) {
      setHtml("errors", `<div class='err'>${data.errors.map((e) => `<div>• ${e}</div>`).join("")}</div>`);
    }
  } catch (err) {
    setHtml("status", `<span class='err'>ERROR</span>`);
    setHtml("errors", `<div class='err'>${String(err)}</div>`);
  }
}

async function runIdentify() {
  const inputText = q("identifyText").value;
  setHtml("identifyStatus", "<span class='warn'>Identifying...</span>");
  setHtml("identifyResult", "");
  setHtml("identifyErrors", "");

  try {
    const res = await fetch("/api/identify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_text: inputText }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || data.error || "Identification failed");
    }

    setHtml("identifyStatus", `<span class='ok'>${data.object_class.toUpperCase()}</span> · ${data.search_radius_arcsec.toFixed(1)} arcsec`);
    setHtml("identifyResult", `
      <div><b>Input:</b> ${data.input_text}</div>
      <div style="margin-top:6px">${data.description}</div>
      <div class="meta" style="margin-top:6px">Top catalogs: ${data.top_catalogs.join(", ")}</div>
      <div class="meta">Reasoning: ${data.reasoning}</div>
    `);
  } catch (err) {
    setHtml("identifyStatus", `<span class='err'>ERROR</span>`);
    setHtml("identifyErrors", `<div class='err'>${String(err)}</div>`);
  }
}

q("runBtn").addEventListener("click", runQuery);
q("clearBtn").addEventListener("click", () => {
  ["status", "summary", "catalogs", "sources", "errors"].forEach((id) => setHtml(id, id === "status" ? "Idle." : ""));
});
q("identifyBtn").addEventListener("click", runIdentify);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.post("/api/query")
async def run_query(request: QueryRequest):
    return await orchestrator.execute_query(request)


@app.post("/api/identify")
async def run_identify(request: IdentifyRequest):
  try:
    result = identify_object(request.input_text)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  return {
    "status": "success",
    "input_text": result.input_text,
    "object_class": result.object_class.value,
    "description": result.description,
    "search_radius_arcsec": result.search_radius_arcsec,
    "top_catalogs": result.top_catalogs,
    "reasoning": result.reasoning,
  }


def main() -> None:
    """Run AstroBridge web app with uvicorn."""
    import uvicorn

    uvicorn.run("astrobridge.web.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
