from collections import OrderedDict


class TileCache:
    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.hits = 0
        self.misses = 0
        self._entries = OrderedDict()

    def get(self, key, load):
        if key in self._entries:
            self.hits += 1
            return self._entries[key]
        self.misses += 1
        value = load(key)
        if len(self._entries) >= self.capacity:
            self._entries.popitem(last=False)
        self._entries[key] = value
        return value
