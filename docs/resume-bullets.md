# ParkGuard Resume Bullets

Use/adapt these bullets in your resume or LinkedIn.

## Short version (1 line)

Built `ParkGuard API`, a FastAPI-based parking intelligence module for connected vehicles, integrating NYC Open Data to return real-time curb compliance decisions and ticket-risk estimates.

## Standard version (3 bullets)

- Developed a production-style FastAPI service that evaluates curb rules (street cleaning, hydrant clearance, loading/truck zones, taxi/FHV zones, official-only spots) and outputs a vehicle-ready decision (`safe/caution/blocked`).
- Implemented rule engines for time windows and proximity checks, plus profile-aware eligibility logic (`vehicle_type`, `commercial_plate`, `agency_affiliation`) for realistic city parking scenarios.
- Added violation-risk modeling with configurable fine bands (`data/nyc_fines.json`), integration/unit test coverage, and a demo HMI dashboard simulating OTA in-vehicle integration.

## Interview version (impact framing)

- Designed ParkGuard as a B2B integration module rather than a consumer app, with typed API contracts and explainable decisions to fit automotive software workflows.
- Combined live public data ingestion, caching, deterministic rule logic, and test automation to reduce API flakiness and improve confidence in parking compliance recommendations.
- Shipped an end-to-end technical demo (backend + UI + tests + documentation) that can be shown to connected-vehicle teams as an integration proof-of-concept.

## Keywords (ATS-friendly)

FastAPI, Python, REST API, Pydantic, rule engine, geospatial logic, NYC Open Data, caching, API integration testing, connected vehicles, OTA software, parking compliance.
