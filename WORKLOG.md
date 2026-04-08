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
