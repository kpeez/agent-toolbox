#!/usr/bin/env python3
"""Validate the retained artifacts of one autoresearch experiment group."""

from __future__ import annotations

import csv
import hashlib
import math
import re
import subprocess
import sys
from pathlib import Path

HEADER = [
    "experiment",
    "commit",
    "evaluator_sha256",
    "primary_metric",
    "guardrails",
    "outcome",
    "decision",
    "elapsed_seconds",
    "artifact_dir",
    "summary",
]
VALID_OUTCOMES = {"completed", "invalid", "crash", "timeout", "evaluator_tamper"}
VALID_DECISIONS = {"keep", "discard", "inconclusive"}
VALID_RESULTS = {
    ("completed", "keep"),
    ("completed", "discard"),
    ("invalid", "discard"),
    ("crash", "inconclusive"),
    ("timeout", "inconclusive"),
    ("evaluator_tamper", "inconclusive"),
}
VALID_TERMINAL_STATES = {
    "threshold_met",
    "budget_exhausted",
    "stop_condition",
    "evaluator_invalid",
    "environment_invalid",
    "safety_stop",
    "user_stopped",
}
PROGRAM_FIELDS = (
    "Problem",
    "Desired outcome",
    "Baseline commit",
    "Baseline result",
    "Primary metric",
    "Metric direction",
    "Guardrails",
    "Evaluator command",
    "Evaluator output contract",
    "Protected paths",
    "Evaluator hash command",
    "Evaluator SHA-256",
    "Mutable paths",
    "Forbidden paths",
    "Per-evaluation timeout seconds",
    "Per-evaluation compute cost limit",
    "Candidate budget",
    "Evaluator-time budget seconds",
    "Compute-cost budget",
    "Meaningful improvement or retest rule",
    "Acceptance threshold",
    "Keep rule",
    "Discard rule",
    "Inconclusive rule",
    "Crash rule",
    "Timeout rule",
    "Evaluator-tamper rule",
    "Rollback rule",
    "Stop conditions",
    "Approval record",
    "Sandbox/network/dependency/credential boundaries",
    "Environment identity",
    "Dependency lock",
    "Seeds",
    "Ledger header",
    "Artifact record format",
)


def field(text: str, name: str, source: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(\S.*?)\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"{source} is missing '{name}: ...'")
    return match.group(1)


def git(worktree: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(worktree), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git validation failed")
    return result.stdout.strip()


def protected_path_values(protected_paths: str) -> list[Path]:
    values = []
    for value in protected_paths.split(";"):
        relative = Path(value.strip())
        if not value.strip() or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                "program.md Protected paths must be semicolon-separated relative paths"
            )
        values.append(relative)
    return values


def evaluator_digest(
    worktree: Path, protected_paths: str, commit: str | None = None
) -> str:
    records = []
    for relative in protected_path_values(protected_paths):
        if commit is not None:
            result = subprocess.run(
                ["git", "-C", str(worktree), "show", f"{commit}:{relative.as_posix()}"],
                check=False,
                capture_output=True,
            )
            if result.returncode:
                raise ValueError(
                    f"protected path missing from commit {commit}: {relative}"
                )
            contents = result.stdout
            records.append(
                f"{relative.as_posix()}\t{hashlib.sha256(contents).hexdigest()}\n"
            )
            continue
        path = (worktree / relative).resolve()
        try:
            path.relative_to(worktree.resolve())
        except ValueError as error:
            raise ValueError(f"protected path escapes worktree: {relative}") from error
        if not path.is_file():
            raise ValueError(f"protected path does not exist: {relative}")
        records.append(
            f"{relative.as_posix()}\t{hashlib.sha256(path.read_bytes()).hexdigest()}\n"
        )
    return hashlib.sha256("".join(sorted(records)).encode()).hexdigest()


def finite_number(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be numeric") from error
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


def numeric(value: str, name: str) -> float:
    parsed = finite_number(value, name)
    if parsed < 0:
        raise ValueError(f"{name} must not be negative")
    return parsed


def nonnegative_integer(value: str, name: str) -> int:
    parsed = numeric(value, name)
    if parsed % 1 != 0:
        raise ValueError(f"{name} must be an integer")
    return int(parsed)


def validate_artifact(artifact_dir: Path, record: dict[str, str], number: int) -> float:
    source = f"results.tsv row {number} artifact README.md"
    readme_path = artifact_dir / "README.md"
    log_path = artifact_dir / "LOG.md"
    if not readme_path.is_file():
        raise ValueError(f"results.tsv row {number} artifact is missing README.md")
    if not log_path.is_file() or not log_path.read_text().strip():
        raise ValueError(
            f"results.tsv row {number} artifact is missing nonempty LOG.md"
        )
    for directory in ("logs", "scripts"):
        if not (artifact_dir / directory).is_dir():
            raise ValueError(
                f"results.tsv row {number} artifact is missing {directory}/"
            )
    readme = readme_path.read_text()
    fields = {
        name: field(readme, name, source)
        for name in (
            "Hypothesis",
            "Planned change",
            "Parent best commit",
            "Candidate commit",
            "Evaluator SHA-256",
            "Primary metric",
            "Guardrails",
            "Outcome",
            "Elapsed seconds",
            "Compute cost",
            "Decision",
            "Decision reason",
            "Rollback proof",
        )
    }
    expected = {
        "Candidate commit": record["commit"],
        "Evaluator SHA-256": record["evaluator_sha256"],
        "Primary metric": record["primary_metric"],
        "Guardrails": record["guardrails"],
        "Outcome": record["outcome"],
        "Elapsed seconds": record["elapsed_seconds"],
        "Decision": record["decision"],
    }
    for name, value in expected.items():
        if fields[name] != value:
            raise ValueError(f"{source} {name} differs from results.tsv")
    return numeric(fields["Compute cost"], f"{source} Compute cost")


def validate(root: Path) -> None:
    program_path = root / "program.md"
    readme_path = root / "README.md"
    ledger_path = root / "results.tsv"
    for path in (program_path, readme_path, ledger_path):
        if not path.is_file():
            raise ValueError(f"missing required artifact: {path.name}")

    program = program_path.read_bytes()
    readme = readme_path.read_text()
    program_digest = field(readme, "Program SHA-256", "README.md")
    actual_digest = hashlib.sha256(program).hexdigest()
    if program_digest != actual_digest:
        raise ValueError("Program SHA-256 does not match program.md")

    program_text = program.decode()
    program_fields = {
        name: field(program_text, name, "program.md") for name in PROGRAM_FIELDS
    }
    if program_fields["Metric direction"] not in {"maximize", "minimize"}:
        raise ValueError("program.md Metric direction must be maximize or minimize")
    evaluator_hash = program_fields["Evaluator SHA-256"]
    if not re.fullmatch(r"[0-9a-f]{64}", evaluator_hash):
        raise ValueError(
            "program.md Evaluator SHA-256 must be 64 lowercase hex characters"
        )

    terminal_state = field(readme, "Terminal state", "README.md")
    if terminal_state not in VALID_TERMINAL_STATES:
        raise ValueError(f"invalid terminal state: {terminal_state}")

    worktree_value = field(readme, "Worktree", "README.md")
    worktree = Path(worktree_value)
    if not worktree.is_absolute():
        worktree = (root / worktree).resolve()
    if not worktree.is_dir():
        raise ValueError(f"worktree does not exist: {worktree_value}")
    if evaluator_digest(worktree, program_fields["Protected paths"]) != evaluator_hash:
        raise ValueError("Evaluator SHA-256 does not match protected paths")

    per_evaluation_timeout = numeric(
        program_fields["Per-evaluation timeout seconds"],
        "program.md Per-evaluation timeout seconds",
    )
    per_evaluation_compute_limit = numeric(
        program_fields["Per-evaluation compute cost limit"],
        "program.md Per-evaluation compute cost limit",
    )
    candidate_budget = nonnegative_integer(
        program_fields["Candidate budget"], "program.md Candidate budget"
    )
    evaluator_time_budget = numeric(
        program_fields["Evaluator-time budget seconds"],
        "program.md Evaluator-time budget seconds",
    )
    compute_cost_budget = numeric(
        program_fields["Compute-cost budget"], "program.md Compute-cost budget"
    )

    with ledger_path.open(newline="") as ledger:
        rows = list(csv.reader(ledger, delimiter="\t"))
    if not rows or rows[0] != HEADER:
        raise ValueError("results.tsv header must be the fixed 10-column ledger header")
    if len(rows) < 2:
        raise ValueError("results.tsv is missing the baseline row")

    data_rows = rows[1:]
    best_commit = ""
    evaluator_seconds_consumed = 0.0
    compute_cost_consumed = 0.0
    for number, row in enumerate(data_rows, start=2):
        if len(row) != 10:
            raise ValueError(
                f"results.tsv row {number} has {len(row)} columns; expected 10"
            )
        record = dict(zip(HEADER, row, strict=True))
        if number == 2 and (
            record["outcome"] != "completed" or record["decision"] != "baseline"
        ):
            raise ValueError("the first results.tsv row must be the completed baseline")
        if number > 2 and record["outcome"] not in VALID_OUTCOMES:
            raise ValueError(
                f"results.tsv row {number} has invalid outcome: {record['outcome']}"
            )
        if number > 2 and record["decision"] not in VALID_DECISIONS:
            raise ValueError(
                f"results.tsv row {number} has invalid decision: {record['decision']}"
            )
        if number > 2 and (record["outcome"], record["decision"]) not in VALID_RESULTS:
            raise ValueError(
                f"results.tsv row {number} has incoherent outcome and decision"
            )
        if record["evaluator_sha256"] != evaluator_hash:
            raise ValueError(
                f"results.tsv row {number} evaluator hash differs from program.md"
            )
        elapsed_seconds = numeric(
            record["elapsed_seconds"], f"results.tsv row {number} elapsed_seconds"
        )
        if record["outcome"] == "completed":
            finite_number(
                record["primary_metric"],
                f"results.tsv row {number} primary_metric",
            )
        if elapsed_seconds > per_evaluation_timeout:
            raise ValueError(f"results.tsv row {number} exceeds per-evaluation timeout")
        evaluator_seconds_consumed += elapsed_seconds

        commit = record["commit"]
        resolved_commit = git(worktree, "rev-parse", "--verify", f"{commit}^{{commit}}")
        if commit != resolved_commit:
            raise ValueError(
                f"results.tsv row {number} commit is not a full commit object ID"
            )
        if (
            evaluator_digest(worktree, program_fields["Protected paths"], commit)
            != evaluator_hash
        ):
            raise ValueError(
                f"results.tsv row {number} commit protected files differ from approved evaluator"
            )

        artifact_value = Path(record["artifact_dir"])
        if artifact_value.is_absolute():
            raise ValueError(f"results.tsv row {number} artifact_dir must be relative")
        artifact_dir = (root / artifact_value).resolve()
        try:
            artifact_dir.relative_to(root)
        except ValueError as error:
            raise ValueError(
                f"results.tsv row {number} artifact_dir escapes the group"
            ) from error
        if not artifact_dir.is_dir():
            raise ValueError(f"results.tsv row {number} artifact_dir does not exist")
        compute_cost = validate_artifact(artifact_dir, record, number)
        if compute_cost > per_evaluation_compute_limit:
            raise ValueError(
                f"results.tsv row {number} exceeds per-evaluation compute cost limit"
            )
        compute_cost_consumed += compute_cost

        if record["decision"] in {"baseline", "keep"}:
            best_commit = commit

    if data_rows[0][1] != program_fields["Baseline commit"]:
        raise ValueError("program.md Baseline commit differs from results.tsv")

    recorded_best = field(readme, "Best commit", "README.md")
    if recorded_best != best_commit:
        raise ValueError(
            "README.md Best commit is not the last baseline or keep commit"
        )
    if git(worktree, "rev-parse", "HEAD") != best_commit:
        raise ValueError("worktree HEAD is not the best commit for resume")
    if git(worktree, "status", "--porcelain"):
        raise ValueError("worktree is not clean for resume")

    threshold = finite_number(
        program_fields["Acceptance threshold"],
        "program.md Acceptance threshold",
    )
    best_metric = finite_number(
        next(row[3] for row in reversed(data_rows) if row[6] in {"baseline", "keep"}),
        "best primary metric",
    )
    candidates_consumed = nonnegative_integer(
        field(readme, "Candidates consumed", "README.md"),
        "README.md Candidates consumed",
    )
    recorded_evaluator_seconds = numeric(
        field(readme, "Evaluator seconds consumed", "README.md"),
        "README.md Evaluator seconds consumed",
    )
    recorded_compute_cost = numeric(
        field(readme, "Compute cost consumed", "README.md"),
        "README.md Compute cost consumed",
    )
    actual_candidates = len(data_rows) - 1
    if candidates_consumed != actual_candidates:
        raise ValueError("README.md Candidates consumed differs from results.tsv")
    if not math.isclose(recorded_evaluator_seconds, evaluator_seconds_consumed):
        raise ValueError(
            "README.md Evaluator seconds consumed differs from results.tsv"
        )
    if not math.isclose(recorded_compute_cost, compute_cost_consumed):
        raise ValueError(
            "README.md Compute cost consumed differs from experiment records"
        )
    if actual_candidates > candidate_budget:
        raise ValueError("results.tsv exceeds Candidate budget")
    if evaluator_seconds_consumed > evaluator_time_budget:
        raise ValueError("results.tsv exceeds Evaluator-time budget")
    if compute_cost_consumed > compute_cost_budget:
        raise ValueError("experiment records exceed Compute-cost budget")
    if terminal_state == "threshold_met":
        direction = program_fields["Metric direction"]
        if (direction == "maximize" and best_metric < threshold) or (
            direction == "minimize" and best_metric > threshold
        ):
            raise ValueError(
                "threshold_met terminal state does not meet Acceptance threshold"
            )
    if terminal_state == "budget_exhausted" and not (
        candidates_consumed == candidate_budget
        or math.isclose(evaluator_seconds_consumed, evaluator_time_budget)
        or math.isclose(compute_cost_consumed, compute_cost_budget)
    ):
        raise ValueError("budget_exhausted terminal state has no exhausted budget")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} GROUP_DIR", file=sys.stderr)
        return 2
    try:
        validate(Path(sys.argv[1]).resolve())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"invalid autoresearch run: {error}", file=sys.stderr)
        return 1
    print("autoresearch artifacts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
