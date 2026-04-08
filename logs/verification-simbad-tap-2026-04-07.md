# Verification Log - SIMBAD TAP Adapter - 2026-04-07

## Scope
- Add live SIMBAD TAP adapter alongside deterministic connectors.
- Keep local deterministic path intact for CI and deterministic tests.

## Commands Run
1. ./.venv/bin/python -m pytest -ra

## Results
- 73 passed, 0 failed.

## Notes
- Live adapter dependency is optional and exposed via setup extra: [live].
- Adapter class: SimbadTapAdapter in astrobridge/connectors.py.
- Live network query execution not validated in CI path.
