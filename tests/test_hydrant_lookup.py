import unittest

from hydrant_lookup import _extract_lat_lon


class HydrantLookupParsingTests(unittest.TestCase):
    def test_extract_flat_lat_lon(self) -> None:
        row = {"latitude": "40.7580", "longitude": "-73.9855"}
        lat, lon = _extract_lat_lon(row)
        self.assertEqual(lat, 40.7580)
        self.assertEqual(lon, -73.9855)

    def test_extract_location_object_lat_lon(self) -> None:
        row = {"location": {"latitude": "40.7580", "longitude": "-73.9855"}}
        lat, lon = _extract_lat_lon(row)
        self.assertEqual(lat, 40.7580)
        self.assertEqual(lon, -73.9855)

    def test_extract_geojson_coordinates(self) -> None:
        row = {"the_geom": {"coordinates": [-73.9855, 40.7580]}}
        lat, lon = _extract_lat_lon(row)
        self.assertEqual(lat, 40.7580)
        self.assertEqual(lon, -73.9855)

    def test_extract_missing(self) -> None:
        lat, lon = _extract_lat_lon({"foo": "bar"})
        self.assertIsNone(lat)
        self.assertIsNone(lon)


if __name__ == "__main__":
    unittest.main()
