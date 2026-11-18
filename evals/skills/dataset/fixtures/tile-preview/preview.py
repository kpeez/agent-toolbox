import time

from renderer import render_tiles

PALETTE_SIZE = 3000
TILE_COUNT = 18000


def palette_entries():
    return [(f" Shade-{i:04d} ", f"#{i * 5591 % 0xFFFFFF:06X}") for i in range(PALETTE_SIZE)]


def tiles():
    return [{"id": f"tile-{i:05d}", "colors": [f"shade-{(i * 7 + k) % PALETTE_SIZE:04d}" for k in range(4)]}
            for i in range(TILE_COUNT)]


def main():
    entries, items = palette_entries(), tiles()
    started = time.perf_counter()
    rows = render_tiles(items, entries)
    elapsed = time.perf_counter() - started
    print(f"rendered {len(rows)} tiles in {elapsed:.1f} s")


if __name__ == "__main__":
    main()
