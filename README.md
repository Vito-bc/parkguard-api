# ParkGuard API

Real-time NYC parking rules API prototype for connected vehicles (OTA-style integration demo).

## What it does

- Returns parking-related rules for a location (`lat`, `lon`, `radius`)
- Combines NYC Open Data parking regulations and parking meter data
- Produces vehicle-friendly JSON (`rules`, `warning`, `confidence`)
- Returns an aggregated vehicle-ready decision (`safe` / `caution` / `blocked`)
- Adds rule-level NYC ticket estimates (`violation_estimate`) when parking is not valid
- Adds response-level fine aggregation (`violation_summary`)
- Uses typed response models (Pydantic) for stable integration contracts
- Includes recurring time-window rule engine for street cleaning countdowns
- Includes demo fallback response if upstream datasets are unavailable

## API Endpoint

`GET /parking-status?lat=40.7580&lon=-73.9855&radius=50&vehicle_type=passenger&commercial_plate=false&agency_affiliation=none`

Example response (shape):

```json
{
  "location": {
    "lat": 40.758,
    "lon": -73.9855,
    "radius_m": 50,
    "address": "NYC address lookup not implemented yet",
    "timestamp": "2026-02-22T19:30:00+00:00"
  },
  "vehicle_profile": {
    "vehicle_type": "passenger",
    "commercial_plate": false,
    "agency_affiliation": "none"
  },
  "rules": [
    {
      "type": "street_cleaning",
      "description": "Alternate Side Parking",
      "next_cleaning": "2026-02-23T19:30:00+00:00",
      "window": "06:00 - 09:00",
      "time_left": "24h 0m",
      "valid": true,
      "source": "NYC DOT Sweeping Schedule"
    },
    {
      "type": "hydrant_proximity",
      "description": "Fire hydrant clearance rule",
      "distance_ft": 12.0,
      "threshold_ft": 15.0,
      "valid": false,
      "reason": "Too close to hydrant: 12.0 ft (minimum 15 ft).",
      "source": "ParkGuard Hydrant Proximity (demo scaffold)",
      "violation_estimate": {
        "violation_code": "NYC-HYDRANT-15FT",
        "min_fine_usd": 115,
        "max_fine_usd": 115,
        "jurisdiction": "NYC",
        "confidence": 0.95
      }
    }
  ],
  "parking_decision": {
    "status": "blocked",
    "risk_score": 97,
    "primary_reason": "Too close to hydrant: 12.0 ft (minimum 15 ft).",
    "recommended_action": "Do not park here. Move to another spot."
  },
  "violation_summary": {
    "estimated_total_min_usd": 115,
    "estimated_total_max_usd": 115,
    "highest_single_max_usd": 115,
    "high_risk_violations": 1,
    "currency": "USD"
  },
  "confidence": 0.98,
  "warning": "Too close to hydrant: 12.0 ft (minimum 15 ft)."
}
```

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger UI:

- `http://127.0.0.1:8000/docs`
- Demo dashboard (mock in-car screen): `http://127.0.0.1:8000/demo`

Run tests:

```bash
python -m unittest discover -s tests -v
```

Includes:
- unit tests for rule/proximity/hydrant parsing
- integration tests for `/parking-status` and `/demo` via FastAPI `TestClient`

## Project direction

ParkGuard is designed as a B2B parking intelligence module for connected vehicles (Toyota / Hyundai / Kia / Rivian / Ford / GM style integration), not only as a standalone app.

Status: MVP in progress

## Roadmap (high-value parking rules)

- Truck / loading-only restrictions (vehicle profile support added; dataset-specific parsing needs refinement)
- Taxi / FHV-only curb zones (vehicle profile support added; sign parsing is heuristic for MVP)
- Hydrant proximity rule (demo scaffold via `hydrant_distance_ft`; wire real hydrant dataset next)
- Hydrant proximity rule (auto lookup from NYC hydrant datasets with optional `hydrant_distance_ft` override)
- Fire / official-only curb zones (heuristic sign parsing + agency profile support)
- Jurisdiction-specific ticket fine catalog (MVP mapping added for core NYC rule types)
- In-memory TTL caching for upstream NYC Open Data requests (demo stability / lower request volume)

## Hydrant Lookup Notes

- ParkGuard now attempts automatic nearest-hydrant lookup from NYC Open Data hydrant datasets (`5bgh-vtsn`, fallback `6pui-xhxz`)
- `hydrant_distance_ft` remains available as a manual override for demo/testing scenarios
