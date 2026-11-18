Rain-gauge readings arrive as files in `inbox/`. Each night the scheduler runs:

    python3 nightly_import.py --inbox inbox --out out/readings.jsonl

It reads every CSV, JSON, and JSON Lines file in the inbox through `pipeline.import_file`
and writes one JSON line per reading. `python3 show.py PATH` prints the readings of one
file. Every adapter (`csv_adapter.py`, `json_adapter.py`, `jsonl_adapter.py`), the
validator (with `schema.json`), and the normalizer (with `aliases.json`) take file paths.
`python3 -m unittest` runs the tests.
