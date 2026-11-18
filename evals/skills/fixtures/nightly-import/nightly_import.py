import argparse
import json
from pathlib import Path

from pipeline import ADAPTERS, import_file


def run(inbox, out, schema_path="schema.json", aliases_path="aliases.json"):
    rows = []
    for path in sorted(Path(inbox).iterdir()):
        if path.suffix in ADAPTERS:
            rows.extend(import_file(path, schema_path, aliases_path))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", default="inbox")
    parser.add_argument("--out", default="out/readings.jsonl")
    args = parser.parse_args()
    print(f"imported {run(args.inbox, args.out)} readings")


if __name__ == "__main__":
    main()
