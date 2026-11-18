import json
from pathlib import Path


def display_name(product):
    return product["display_name"]


def load_products(path="products.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))
