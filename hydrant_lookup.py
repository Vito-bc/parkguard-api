from __future__ import annotations

from math import cos, radians
from typing import Any

import requests

from proximity_engine import distance_meters, meters_to_feet

NYC_HYDRANT_DATASET_IDS = ("5bgh-vtsn", "6pui-xhxz")
REQUEST_TIMEOUT_SECONDS = 4


def _fetch_json(url: str) -> list[dict[str, Any]]:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except (requests.RequestException, ValueError):
        return []


def _extract_lat_lon(record: dict[str, Any]) -> tuple[float | None, float | None]:
    # Common flat field names in Socrata tables.
    lat_keys = ("latitude", "lat", "y", "y_coord", "ycoord")
    lon_keys = ("longitude", "long", "lon", "x", "x_coord", "xcoord")

    for lat_key in lat_keys:
        for lon_key in lon_keys:
            if lat_key in record and lon_key in record:
                try:
                    return float(record[lat_key]), float(record[lon_key])
                except (TypeError, ValueError):
                    pass

    # Socrata "location" object patterns.
    for key in ("location", "point", "the_geom", "geom", "geometry"):
        value = record.get(key)
        if isinstance(value, dict):
            if "latitude" in value and "longitude" in value:
                try:
                    return float(value["latitude"]), float(value["longitude"])
                except (TypeError, ValueError):
                    pass
            if "coordinates" in value and isinstance(value["coordinates"], list) and len(value["coordinates"]) >= 2:
                try:
                    lon, lat = value["coordinates"][0], value["coordinates"][1]
                    return float(lat), float(lon)
                except (TypeError, ValueError):
                    pass

    return None, None


def _query_dataset_candidates(dataset_id: str, lat: float, lon: float, radius_m: int) -> list[dict[str, Any]]:
    # Try geospatial query first (works for some views with the_geom)
    geo_url = (
        f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
        f"?$where=within_circle(the_geom, {lat}, {lon}, {radius_m})&$limit=50"
    )
    rows = _fetch_json(geo_url)
    if rows:
        return rows

    # Fallback to lat/lon bbox queries with common column names.
    lat_delta = radius_m / 111_000
    lon_scale = max(cos(radians(lat)), 0.1)
    lon_delta = radius_m / (111_000 * lon_scale)
    min_lat, max_lat = lat - lat_delta, lat + lat_delta
    min_lon, max_lon = lon - lon_delta, lon + lon_delta

    lat_candidates = ("latitude", "lat", "y")
    lon_candidates = ("longitude", "long", "lon", "x")
    for lat_field in lat_candidates:
        for lon_field in lon_candidates:
            bbox_url = (
                f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
                f"?$where={lat_field} between {min_lat} and {max_lat} and {lon_field} between {min_lon} and {max_lon}"
                "&$limit=200"
            )
            rows = _fetch_json(bbox_url)
            if rows:
                return rows

    return []


def find_nearest_hydrant_distance_ft(
    *,
    lat: float,
    lon: float,
    search_radius_m: int = 75,
) -> tuple[float | None, str | None]:
    best_distance_m: float | None = None
    best_dataset: str | None = None

    for dataset_id in NYC_HYDRANT_DATASET_IDS:
        rows = _query_dataset_candidates(dataset_id, lat, lon, search_radius_m)
        for row in rows:
            row_lat, row_lon = _extract_lat_lon(row)
            if row_lat is None or row_lon is None:
                continue
            d_m = distance_meters(lat, lon, row_lat, row_lon)
            if best_distance_m is None or d_m < best_distance_m:
                best_distance_m = d_m
                best_dataset = dataset_id

        if best_distance_m is not None:
            # Prefer first dataset that yields a result to limit latency.
            break

    if best_distance_m is None:
        return None, None

    return round(meters_to_feet(best_distance_m), 1), best_dataset
