# Work Log

## 2026-04-07

### Completed
- Enabled async pytest support with project-level config in pytest.ini.
- Cleaned Pydantic v2 schema config warnings in astrobridge/api/schemas.py.
- Improved packaging metadata and added installable demo command via setup.py.
- Added onboarding and usage documentation in README.md.
- Made phase 6 demo self-contained by registering synthetic connectors in demo.py.
- Updated orchestrator natural-language query path in astrobridge/api/orchestrator.py.
- Verified quality gate: 71 passed, 2 skipped, 0 failed.
- Verified runtime gate: astrobridge-demo completes successfully.

### Decisions
- Keep integration connector tests skipped until live connector methods (for example cone_search) are implemented.
- Keep demo data synthetic for predictable local runs and contributor onboarding.

### Next Step
- Implement production connectors with real external catalog access and explicit timeout/retry policies.

### Next Step Progress
- Added async-compatible connector methods (`query_object`, `cone_search`) in astrobridge/connectors.py to establish the integration API surface for live-catalog work.

### 2026-04-07 Connector Milestone
- Implemented deterministic local datasets and query logic for SimbadConnector and NEDConnector.
- Implemented radius-based cone search behavior for both connectors.
- Enabled integration matching tests by removing the cone_search skip gate.
- Updated integration assertions to use MatchResult fields (`source1_id`, `source2_id`).
- Re-verified quality gate: 73 passed, 0 skipped, 0 failed.

### Updated Next Step
- Replace deterministic local connector datasets with live external catalog adapters and resilience controls.

### 2026-04-07 SIMBAD TAP Milestone
- Added optional live adapter class SimbadTapAdapter in astrobridge/connectors.py.
- Adapter supports object lookup and cone search through SIMBAD TAP ADQL queries.
- Added setup extra [live] with pyvo dependency in setup.py.
- Documented activation and usage in README.md.
- Re-verified local quality gate after changes: 73 passed, 0 failed.

### Updated Next Step (Live Data)
- Add NED live adapter with the same error handling and normalization pattern as SIMBAD TAP.
- Add adapter-level timeout/retry/rate-limit configuration hooks.

### 2026-04-07 NED TAP + Test-Coupled Development
- Added NedTapAdapter in astrobridge/connectors.py with async `query_object` and `cone_search` TAP flow.
- Made live TAP adapters dependency-injectable (`tap_service`) to support network-free tests.
- Added adapter test suite in tests/test_live_adapters.py.
- Re-verified full suite after this step: 78 passed, 0 failed.

### Updated Next Step (Reliability)
- Add retry/timeout wrappers to SimbadTapAdapter and NedTapAdapter.
- Add failure-path tests for TAP exceptions and malformed rows.

### 2026-04-07 TAP Reliability + Failure Coverage
- Added timeout controls and retry/backoff loops to SimbadTapAdapter and NedTapAdapter.
- Added safe numeric parsing fallbacks for malformed TAP row fields.
- Added failure-path tests in tests/test_live_adapters.py for retry success, retry exhaustion, timeout behavior, and malformed row handling.
- Re-verified full quality gate after this step: 82 passed, 0 failed.

### Updated Next Step (Operational Hardening)
- Add configurable per-adapter logging context (request IDs/query tags) for observability.
- Add optional jittered retry delay and max query size guards.

## 2026-04-08

### Completed
- Added dedicated confidence scoring module in astrobridge/matching/confidence.py.
- Integrated confidence scoring into BayesianMatcher output path.
- Added confidence-focused test coverage in tests/test_confidence_scoring.py.
- Added proper-motion fields to Coordinate model and proper-motion-aware matching mode in BayesianMatcher.
- Added epoch-aware matching tests in tests/test_matcher.py.
- Added pipeline-level integration test for epoch-aware cross-match behavior in tests/integration/test_matching_pipeline.py.
- Re-verified quality gate after each step and full run.

### Verification
- Full suite passing: 98 passed, 0 failed.

### Updated Next Step
- Add configurable multi-attribute weighting profiles (spatial vs photometric vs future redshift signals).
- Expose proper_motion_aware and weighting profile controls through API request schemas and orchestrator flow.

### 2026-04-08 API Matcher Controls
- Exposed matcher controls in QueryRequest: proper_motion_aware, match_epoch, astrometric_weight, photometric_weight.
- Wired AstroBridgeOrchestrator to apply request-level matcher controls before execution.
- Added API tests for schema validation and matcher-control propagation.
- Verification gate: tests/test_api.py passing.

### 2026-04-08 Weighting Profiles
- Added confidence weighting profiles: balanced, position_first, photometry_first.
- Added ConfidenceScorer.from_profile factory and profile-aware scoring explanations.
- Exposed `weighting_profile` in QueryRequest and orchestrator control application.
- Added/updated tests in tests/test_confidence_scoring.py and tests/test_api.py.
- Verification gate: full suite passing (106/106).

### 2026-04-08 Minimal Web Frontend
- Added FastAPI web console at astrobridge/web/app.py.
- Added browser query controls for query type, proper-motion toggle, match epoch, weighting profile, and optional custom weights.
- Added live result panels for query status, catalogs queried, sources returned, and errors.
- Added package extras and CLI entrypoint support for web launch in setup.py (`astrobridge-web`).

### 2026-04-08 Release Automation
- Added a GitHub Actions workflow for tag-triggered PyPI publishing.
- Workflow builds the package and uploads distributions when a `v*` tag is pushed.
- Publishing requires a GitHub secret named `PYPI_API_TOKEN`.

### 2026-04-08 AI Object Identification Command
- Added `astrobridge-identify` as a console script for classifying input text and generating a human-readable object description.
- The command uses the existing NLP router to infer object class, search radius, and top catalogs.
- Added focused tests for the new identification helper and CLI formatting output.

### 2026-04-08 Web Identification Panel
- Added `/api/identify` to the FastAPI web app for live object identification.
- Added an identification panel to the browser UI with inline success and error output.
- Added web tests covering valid identification, blank-input rejection, and page rendering.

### 2026-04-08 Persistent Jobs and Analytics
- Added SQLite persistence for analytics events and asynchronous job records.
- Added `ASTROBRIDGE_STATE_DB` support to configure state database location.
- Added persistence tests to verify data survives store/manager re-instantiation.

### 2026-04-08 Full Package Demo Expansion
- Expanded `demo.py` to cover identification, telemetry, persistence, background jobs, and benchmarking.
- Updated the demo summary to report all currently shipped package capabilities.
- Reframed the documentation so the demo is described as a full package walkthrough.
