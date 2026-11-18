def normalized_palette(entries):
    return {name.strip().casefold(): "#" + code.strip().lstrip("#").lower() for name, code in entries}


def render_tiles(tiles, palette_entries):
    rows = []
    for tile in tiles:
        palette = normalized_palette(palette_entries)
        rows.append({"id": tile["id"], "colors": [palette[name.strip().casefold()] for name in tile["colors"]]})
    return rows
