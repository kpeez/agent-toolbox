from pathlib import Path

from csv_adapter import read_csv
from json_adapter import read_json
from jsonl_adapter import read_jsonl
from normalizer import normalize
from validator import validate

ADAPTERS = {".csv": read_csv, ".json": read_json, ".jsonl": read_jsonl}


def import_file(path, schema_path="schema.json", aliases_path="aliases.json"):
    adapter = ADAPTERS.get(Path(path).suffix)
    if adapter is None:
        raise ValueError(f"unsupported file: {path}")
    return validate(normalize(adapter(path), aliases_path), schema_path)
