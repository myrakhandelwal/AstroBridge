# Verification Log - TAP Reliability and Failure Paths - 2026-04-07

## Scope
- Add timeout and retry logic to both live TAP adapters.
- Add failure-path tests for exception and malformed-row behavior.

## Implementation
- Updated SimbadTapAdapter in astrobridge/connectors.py
  - async timeout guards for query_object and cone_search
  - retry loop for TAP search calls
  - safe float parsing fallback in row mapping
- Updated NedTapAdapter in astrobridge/connectors.py
  - async timeout guards for query_object and cone_search
  - retry loop for TAP search calls
  - safe float parsing fallback in row mapping

## Tests Added/Updated
- tests/test_live_adapters.py
  - retry succeeds after transient failure
  - retry exhaustion returns empty result
  - timeout returns empty result
  - malformed numeric values map to default coordinates

## Commands Run
1. ./.venv/bin/python -m pytest -ra

## Results
- 82 passed, 0 failed
