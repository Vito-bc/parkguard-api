# ParkGuard API

Real-time NYC parking rules API prototype for connected vehicles (OTA-style integration demo).

## What it does

- Returns parking-related rules for a location (`lat`, `lon`, `radius`)
- Combines NYC Open Data parking regulations and parking meter data
- Produces vehicle-friendly JSON (`rules`, `warning`, `confidence`)
- Uses typed response models (Pydantic) for stable integration contracts
- Includes recurring time-window rule engine for street cleaning countdowns
- Includes demo fallback response if upstream datasets are unavailable

## API Endpoint

`GET /parking-status?lat=40.7580&lon=-73.9855&radius=50`

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
  "rules": [
    {
      "type": "street_cleaning",
      "description": "Alternate Side Parking",
      "next_cleaning": "2026-02-23T19:30:00+00:00",
      "window": "06:00 - 09:00",
      "time_left": "24h 0m",
      "valid": true,
      "source": "NYC DOT Sweeping Schedule"
    }
  ],
  "confidence": 0.98,
  "warning": "Cannot park here - street cleaning in 24h 0m"
}
```

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger UI:

- `http://127.0.0.1:8000/docs`

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Project direction

ParkGuard is designed as a B2B parking intelligence module for connected vehicles (Toyota / Hyundai / Kia / Rivian / Ford / GM style integration), not only as a standalone app.

Status: MVP in progress
