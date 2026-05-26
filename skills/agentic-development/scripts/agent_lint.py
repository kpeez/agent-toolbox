#!/usr/bin/env python3
"""Compact ruff + ty wrapper for agents.

Runs `uv run ruff format --check`, `uv run ruff check`, and `uv run ty check`,
writes the full combined log to .agent/lint-last.log, and prints only a
structured JSON summary — keeping agent context windows clean.

Usage:
    python tools/agent_lint.py
    python tools/agent_lint.py src/ tests/
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

MAX_ISSUES = 20


def compact_text(s: str, limit: int = 2000) -> str:
    s = re.sub(r"\n{3,}", "\n\n", s.strip())
    if len(s) <= limit:
        return s
    return s[: limit // 2] + "\n...[truncated]...\n" + s[-limit // 2 :]


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    return proc.returncode, proc.stdout


def check_format(paths: list[str]) -> tuple[dict, str]:
    code, out = run(["uv", "run", "ruff", "format", "--check", *paths])
    # lines like "Would reformat: src/foo.py"
    affected = [
        line.split(": ", 1)[1].strip()
        for line in out.splitlines()
        if line.startswith("Would reformat:")
    ]
    return {
        "status": "passed" if code == 0 else "failed",
        "exit_code": code,
        "files_needing_format": affected,
    }, out


def check_lint(paths: list[str]) -> tuple[dict, str]:
    code, out = run(["uv", "run", "ruff", "check", "--output-format", "json", *paths])
    try:
        raw = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        # ruff emitted non-JSON (e.g. a config error) — surface as-is
        return {
            "status": "failed",
            "exit_code": code,
            "issue_count": None,
            "issues": [],
            "parse_error": compact_text(out),
        }, out

    issues = [
        {
            "code": item.get("code"),
            "file": item.get("filename"),
            "line": item.get("location", {}).get("row"),
            "message": item.get("message"),
            "fixable": item.get("fix") is not None,
        }
        for item in raw[:MAX_ISSUES]
    ]
    return {
        "status": "passed" if code == 0 else "failed",
        "exit_code": code,
        "issue_count": len(raw),
        "issues": issues,
    }, out


def check_types(paths: list[str]) -> tuple[dict, str]:
    code, out = run(["uv", "run", "ty", "check", "--output-format", "concise", *paths])
    lines = [l for l in out.splitlines() if l.strip() and not l.startswith("warning:")]
    # count lines that look like diagnostics: "path:line:col: error[...] msg"
    diag_lines = [l for l in lines if re.match(r".*:\d+:\d+:", l)]
    return {
        "status": "passed" if code == 0 else "failed",
        "exit_code": code,
        "issue_count": len(diag_lines),
        "excerpt": compact_text("\n".join(diag_lines[:MAX_ISSUES])),
    }, out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to check (default: project root).",
    )
    args = parser.parse_args()

    out_dir = Path(".agent")
    out_dir.mkdir(exist_ok=True)
    log_path = out_dir / "lint-last.log"

    fmt_result, fmt_log = check_format(args.paths)
    lint_result, lint_log = check_lint(args.paths)
    types_result, types_log = check_types(args.paths)

    combined_log = "\n".join(
        [
            "=== ruff format --check ===",
            fmt_log,
            "=== ruff check ===",
            lint_log,
            "=== ty check ===",
            types_log,
        ]
    )
    log_path.write_text(combined_log, encoding="utf-8", errors="replace")

    overall = (
        "passed"
        if all(r["status"] == "passed" for r in [fmt_result, lint_result, types_result])
        else "failed"
    )

    result = {
        "status": overall,
        "format": fmt_result,
        "lint": lint_result,
        "typecheck": types_result,
        "full_log": str(log_path),
    }
    if overall != "passed":
        result["note"] = (
            "Full tool output written to disk; inspect it only if the summary is insufficient."
        )

    print(json.dumps(result, indent=2))
    return 0 if overall == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
