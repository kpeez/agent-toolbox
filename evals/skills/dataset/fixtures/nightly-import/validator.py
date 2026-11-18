import json


def load_required(schema_path):
    with open(schema_path, encoding="utf-8") as handle:
        return json.load(handle)["required"]


def validate(rows, schema_path):
    required = load_required(schema_path)
    for index, row in enumerate(rows):
        missing = [field for field in required if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"row {index}: missing {', '.join(missing)}")
    return rows
