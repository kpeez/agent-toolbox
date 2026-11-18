"""Test helper: read the skill-eval corpus as case dicts and write a custom corpus as Inspect Sample JSONL."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import skill_eval as se

DATASET = se.DATASET


def read_cases(path=DATASET):
    return se.read_cases(path)


def write_corpus(path, cases):
    """Write case dicts as one Sample per line; the inverse of skill_eval.read_cases, with no validation."""
    lines = []
    for case in cases:
        fixture = HERE / "fixtures" / case["fixture"]
        files = {p.relative_to(fixture).as_posix(): f"../fixtures/{case['fixture']}/{p.relative_to(fixture).as_posix()}"
                 for p in sorted(fixture.rglob("*")) if p.is_file()}
        metadata = {("target_skill" if k == "target" else k): v for k, v in case.items()
                    if k not in {"id", "messages", "expected_route", "fixture"}}
        sample = {"id": case["id"], "input": case["messages"]}
        if case.get("expected_route") is not None:
            sample["target"] = case["expected_route"]
        lines.append(json.dumps({**sample, "files": files, "metadata": metadata}))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
