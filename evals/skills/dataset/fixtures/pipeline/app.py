from csv_source import read_csv
from json_source import read_json
from validator import validate
from normalizer import normalize

def run_import(kind, text):
    if kind == "csv":
        rows = read_csv(text)
    elif kind == "json":
        rows = read_json(text)
    else:
        raise ValueError("unsupported kind")
    return [normalize(row) for row in validate(rows)]
