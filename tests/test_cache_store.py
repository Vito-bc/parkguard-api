import time
import unittest

from cache_store import TTLCache


class TTLCacheTests(unittest.TestCase):
    def test_set_get_hit(self) -> None:
        cache = TTLCache()
        cache.set("k", {"v": 1}, ttl_seconds=10)
        self.assertEqual(cache.get("k"), {"v": 1})

    def test_expiry(self) -> None:
        cache = TTLCache()
        cache.set("k", 123, ttl_seconds=1)
        time.sleep(1.1)
        self.assertIsNone(cache.get("k"))

    def test_clear(self) -> None:
        cache = TTLCache()
        cache.set("k", 1, ttl_seconds=10)
        cache.clear()
        self.assertIsNone(cache.get("k"))


if __name__ == "__main__":
    unittest.main()
