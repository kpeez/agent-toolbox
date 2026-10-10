def render_tiles(tiles, palette):
    result = []
    for tile in tiles:
        colors = [palette[name] for name in tile["colors"]]
        result.append({"id": tile["id"], "colors": colors})
    return result
