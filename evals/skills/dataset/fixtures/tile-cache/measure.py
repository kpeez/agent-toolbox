import argparse
import bisect
import random

from cache import TileCache

TILE_COUNT = 2000
REQUEST_COUNT = 18000
CAPACITY = 200


def build_trace(seed):
    rng = random.Random(seed)
    weights = [1.0 / (rank ** 1.1) for rank in range(1, TILE_COUNT + 1)]
    cumulative = []
    total = 0.0
    for weight in weights:
        total += weight
        cumulative.append(total)

    trace = []
    prev = 0
    for _ in range(REQUEST_COUNT):
        if trace and rng.random() < 0.25:
            if prev == 0:
                tile_id = 1
            elif prev == TILE_COUNT - 1:
                tile_id = TILE_COUNT - 2
            else:
                tile_id = prev + rng.choice((-1, 1))
        else:
            tile_id = bisect.bisect_left(cumulative, rng.random() * total)
        trace.append(tile_id)
        prev = tile_id
    return trace


def measure(seed):
    trace = build_trace(seed)
    cache = TileCache(capacity=CAPACITY)
    for tile_id in trace:
        cache.get(tile_id, lambda key: f"tile-{key}")
    return cache.hits / (cache.hits + cache.misses)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    print(f"hit_rate={measure(args.seed):.3f}")


if __name__ == "__main__":
    main()
