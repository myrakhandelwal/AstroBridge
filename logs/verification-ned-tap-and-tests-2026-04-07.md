# Verification Log - NED TAP Adapter and Step Tests - 2026-04-07

## Scope
- Add NedTapAdapter for live TAP-based NED access.
- Keep development step coupled to tests in tests/.

## Test Additions
- tests/test_live_adapters.py
  - SIMBAD TAP row mapping and quote escaping test
  - SIMBAD cone search radius guard test
  - NED TAP row mapping test
  - NED cone-search ADQL generation test

## Commands Run
1. ./.venv/bin/python -m pytest -ra

## Results
- 78 passed, 0 failed.

## Notes
- Live adapters support injected TAP services for deterministic, network-free unit tests.
- Live endpoint availability remains an integration concern and should be validated separately.
