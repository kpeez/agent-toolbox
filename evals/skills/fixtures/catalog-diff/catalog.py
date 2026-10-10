def visible_items(items):
    return sorted((item for item in items if not item["archived"]), key=lambda item: item["id"])
