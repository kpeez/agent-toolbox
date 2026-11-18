import unittest

from cache import TileCache


class TileCacheTests(unittest.TestCase):
    def test_hit_returns_cached_value_without_reloading(self):
        calls = []
        cache = TileCache(capacity=2)
        first = cache.get(10, lambda k: calls.append(k) or f"tile-{k}")
        second = cache.get(10, lambda k: calls.append(k) or f"tile-{k}")
        self.assertEqual(first, "tile-10")
        self.assertEqual(second, "tile-10")
        self.assertEqual(calls, [10])
        self.assertEqual((cache.hits, cache.misses), (1, 1))

    def test_miss_calls_load_and_counts_misses(self):
        cache = TileCache(capacity=2)
        self.assertEqual(cache.get(1, lambda k: f"v-{k}"), "v-1")
        self.assertEqual(cache.get(2, lambda k: f"v-{k}"), "v-2")
        self.assertEqual((cache.hits, cache.misses), (0, 2))

    def test_fifo_evicts_oldest_inserted_entry(self):
        calls = []

        def load(key):
            calls.append(key)
            return f"tile-{key}"

        cache = TileCache(capacity=2)
        cache.get(1, load)
        cache.get(2, load)
        cache.get(1, load)
        cache.get(3, load)
        self.assertEqual(cache.get(2, load), "tile-2")
        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(cache.get(1, load), "tile-1")
        self.assertEqual(calls, [1, 2, 3, 1])


if __name__ == "__main__":
    unittest.main()
