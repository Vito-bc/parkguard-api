# ParkGuard API

OTA-style parking intelligence API for connected vehicles.

ParkGuard evaluates curb rules in real time and returns a vehicle-ready decision (`safe`, `caution`, `blocked`) with explainable rule outputs and estimated ticket exposure.

## Why this project

Most navigation products show distance and routes, but not curb-level risk like:
- fire hydrant clearance
- alternate-side cleaning windows
- no-standing windows (e.g., 8:00-18:00 Mon-Fri)
- truck/loading-only restrictions
- taxi/FHV-only zones
- official vehicle-only zones

ParkGuard focuses on that last-mile parking intelligence problem as a B2B integration module.

## Core capabilities

- Rule evaluation for NYC parking contexts
- Aggregated decision output (`parking_decision`)
- Rule-level violation estimates (`violation_estimate`)
- Response-level ticket summary (`violation_summary`)
- Vehicle profile awareness:
  - `vehicle_type`: `passenger | truck | taxi | fhv`
  - `commercial_plate`
  - `agency_affiliation`: `none | police | fire | city | school`
- Hydrant proximity checks (auto lookup + manual override)
- GPS accuracy fallback warning (`hydrant_uncertain`) when hydrant lookup is inconclusive
- In-memory TTL caching for upstream data calls
- Integration and unit test coverage

## API

`GET /parking-status`

Example:

```http
GET /parking-status?lat=40.7580&lon=-73.9855&radius=50&vehicle_type=passenger&commercial_plate=false&agency_affiliation=none
```

High-level response fields:

- `location`
- `vehicle_profile`
- `rules[]`
- `parking_decision`
- `violation_summary`
- `data_freshness`
- `confidence`
- `warning`

Full interactive docs:
- `http://127.0.0.1:8000/docs`

Demo dashboard:
- `http://127.0.0.1:8000/demo`
- `http://127.0.0.1:8000/system-health` (cache stats + latest upstream status)

## Quickstart

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Deploy (Render)

This repo includes `render.yaml`.

Start command:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Fine catalog

Violation fine bands are configured in:

- `data/nyc_fines.json`

This enables non-code updates to estimated fine ranges.

## Repository structure

- `main.py` - FastAPI app and endpoint orchestration
- `sign_parser.py` - parking sign parsing and profile-aware rule conversion
- `decision_engine.py` - aggregate parking decision scoring (`safe/caution/blocked`)
- `meter_parser.py` - meter record normalization into parking rules
- `hydrant_service.py` - hydrant rule assembly and GPS fallback handling
- `rule_engine.py` - recurring time-window logic
- `proximity_engine.py` - distance and clearance evaluation
- `hydrant_lookup.py` - nearest hydrant lookup from NYC Open Data
- `violations.py` - violation estimate and summary logic
- `schemas.py` - typed API models
- `cache_store.py` - in-memory TTL cache
- `demo/index.html` - in-car style UI mock
- `tests/` - integration + unit tests

## Current status

MVP complete for portfolio/demo and early technical outreach.

Next engineering steps:
- parser refactor (`sign_parser` and `decision_engine` separation)
- richer school-zone time logic
- stronger geospatial rule normalization
- production-grade cache/index strategy
