#!/usr/bin/env python3
"""Compact pytest wrapper for agents.

Runs the test suite via `uv run pytest`, writes the full log to
.agent/pytest-last.log, and prints only a structured JSON summary —
keeping agent context windows clean.

Usage:
    python tools/agent_pytest.py -- tests/
    python tools/agent_pytest.py -- tests/test_foo.py -k my_test
"""

import argparse
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def compact_text(s: str, limit: int = 1400) -> str:
    s = re.sub(r"\n{3,}", "\n\n", s.strip())
    if len(s) <= limit:
        return s
    return s[: limit // 2] + "\n...[truncated]...\n" + s[-limit // 2 :]


def parse_junit(xml_path: Path) -> dict:
    if not xml_path.exists():
        return {
            "tests": None,
            "failures": None,
            "errors": None,
            "skipped": None,
            "failed_cases": [],
        }

    root = ET.parse(xml_path).getroot()

    failed_cases = []
    for case in root.iter():
        if not case.tag.endswith("testcase"):
            continue

        failure = None
        kind = None
        for child in case:
            if child.tag.endswith("failure"):
                failure, kind = child, "failure"
                break
            if child.tag.endswith("error"):
                failure, kind = child, "error"
                break

        if failure is None:
            continue

        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "")
        file = case.attrib.get("file", "")
        nodeid = "::".join(x for x in [file or classname, name] if x)

        failed_cases.append(
            {
                "nodeid": nodeid,
                "kind": kind,
                "message": compact_text(failure.attrib.get("message", "").strip(), 400),
                "excerpt": compact_text(failure.text or "", 1600),
            }
        )

    return {
        "tests": int(root.attrib.get("tests", 0)),
        "failures": int(root.attrib.get("failures", 0)),
        "errors": int(root.attrib.get("errors", 0)),
        "skipped": int(root.attrib.get("skipped", 0)),
        "failed_cases": failed_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to pytest (use -- separator).",
    )
    args = parser.parse_args()

    pytest_args = args.pytest_args
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]

    out_dir = Path(".agent")
    out_dir.mkdir(exist_ok=True)
    log_path = out_dir / "pytest-last.log"
    xml_path = out_dir / "pytest-last.xml"

    cmd = [
        "uv",
        "run",
        "pytest",
        "-q",
        "--tb=short",
        "--disable-warnings",
        f"--junitxml={xml_path}",
        *pytest_args,
    ]

    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    log_path.write_text(proc.stdout, encoding="utf-8", errors="replace")

    junit = parse_junit(xml_path)

    if proc.returncode == 0:
        result = {
            "status": "passed",
            "exit_code": proc.returncode,
            "tests": junit["tests"],
            "failures": 0,
            "errors": 0,
            "full_log": str(log_path),
        }
    else:
        result = {
            "status": "failed",
            "exit_code": proc.returncode,
            "tests": junit["tests"],
            "failures": junit["failures"],
            "errors": junit["errors"],
            "skipped": junit["skipped"],
            "failed_cases": junit["failed_cases"][:10],
            "full_log": str(log_path),
            "note": "Full pytest output was written to disk; inspect it only if the summary is insufficient.",
        }

    print(json.dumps(result, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
