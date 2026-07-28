#!/usr/bin/env python3
"""Validate swe workflow artifacts before they're published.

Motivating failure mode: documentation drift -- agents publishing issues that
are missing acceptance criteria, or specs whose status jumps draft -> done
without ever passing through review. Graph nodes run this before publishing
a spec or issue; it enforces the shape, it doesn't just suggest it.

The approval marker is not required on status=archived: an archived spec may
be an abandoned draft that was never approved, so exempting it is intentional.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STATUSES = ("draft", "active", "review", "done", "archived")
FORWARD_ORDER = ("draft", "active", "review", "done")
APPROVAL_MARKER = "<!-- knack:spec-approved -->"

ISSUE_SECTIONS = (
    "## What to build",
    "## Acceptance criteria",
    "## Scope",
    "## Blocked by",
)
CHECKLIST_ITEM_RE = re.compile(r"^- \[[ xX]\]", re.MULTILINE)


class UnclosedFrontmatter(Exception):
    pass


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    frontmatter: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body = "\n".join(lines[i + 1 :])
            return frontmatter, body
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()
    raise UnclosedFrontmatter


def is_legal_transition(previous: str, current: str) -> bool:
    if previous == current:
        return True
    if current == "archived":
        return True
    if previous == "archived":
        return False
    if previous not in FORWARD_ORDER or current not in FORWARD_ORDER:
        return False
    return FORWARD_ORDER.index(current) == FORWARD_ORDER.index(previous) + 1


def validate_spec(text: str, previous_status: str | None) -> list[str]:
    violations: list[str] = []
    try:
        parsed = parse_frontmatter(text)
    except UnclosedFrontmatter:
        violations.append("unclosed YAML frontmatter: file opens with '---' but the block never closes")
        return violations
    if parsed is None:
        violations.append("missing YAML frontmatter: file must open with a '---' delimited block")
        return violations
    frontmatter, body = parsed

    status = frontmatter.get("status")
    if not status:
        violations.append("missing frontmatter key: status")
    if not frontmatter.get("desc"):
        violations.append("missing frontmatter key: desc")
    if status and status not in STATUSES:
        violations.append(f"unknown status: {status}")

    if previous_status is not None and previous_status not in STATUSES:
        violations.append(f"unknown previous status: {previous_status}")
    elif status in STATUSES and previous_status is not None:
        if not is_legal_transition(previous_status, status):
            violations.append(f"illegal transition: {previous_status} -> {status}")

    # archived is exempt: an archived spec may be an abandoned draft that was
    # never approved in the first place.
    if status in ("active", "review", "done") and APPROVAL_MARKER not in body:
        violations.append(f"missing approval marker for status={status}: {APPROVAL_MARKER}")

    return violations


def extract_section(text: str, heading: str) -> str | None:
    idx = text.find(heading)
    if idx == -1:
        return None
    rest = text[idx + len(heading) :]
    next_idx = rest.find("\n## ")
    return rest[:next_idx] if next_idx != -1 else rest


def validate_issue(text: str) -> list[str]:
    violations: list[str] = []
    for heading in ISSUE_SECTIONS:
        if heading not in text:
            violations.append(f"missing section heading: {heading}")

    acceptance_criteria = extract_section(text, "## Acceptance criteria")
    if acceptance_criteria is not None and not CHECKLIST_ITEM_RE.search(acceptance_criteria):
        violations.append("Acceptance criteria section has no checklist items")

    return violations


def read_or_exit(path: str) -> str:
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        raise SystemExit(1) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    spec_parser = subparsers.add_parser("spec", help="Validate a spec's frontmatter and marker")
    spec_parser.add_argument("path")
    spec_parser.add_argument("--previous-status")

    issue_parser = subparsers.add_parser("issue", help="Validate an issue body's required sections")
    issue_parser.add_argument("path", help="path to the issue body, or '-' for stdin")

    args = parser.parse_args()

    if args.command == "spec":
        text = read_or_exit(args.path)
        violations = validate_spec(text, args.previous_status)
    else:
        text = sys.stdin.read() if args.path == "-" else read_or_exit(args.path)
        violations = validate_issue(text)

    if violations:
        for violation in violations:
            print(violation)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
