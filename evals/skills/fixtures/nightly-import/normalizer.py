import json


def load_aliases(aliases_path):
    with open(aliases_path, encoding="utf-8") as handle:
        return json.load(handle)


def normalize(rows, aliases_path):
    aliases = load_aliases(aliases_path)
    return [{aliases.get(key, key): str(value).strip() for key, value in row.items()} for row in rows]
