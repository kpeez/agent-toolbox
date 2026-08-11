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
APPROVAL_KEY = "approved"
EXECUTION_MODE_KEY = "execution_mode"
EXECUTION_MODES = ("autonomous", "review-gated")
TRACKER_KEY = "tracker"
CONTAINER_KEY = "tracker_container"
TRACKERS = ("linear", "github", "local")
# Statuses that mean the spec has been published as real work, so it must carry
# an approval and a container. `archived` is exempt: it may be an abandoned
# draft that was never approved in the first place.
PUBLISHED_STATUSES = ("active", "review", "done")

ISSUE_SECTIONS = (
    "## What to build",
    "## Acceptance criteria",
    "## Scope",
    "## Blocked by",
)
CHECKLIST_ITEM_RE = re.compile(r"^- \[[ xX]\]", re.MULTILINE)

TASKS_HEADING = "## Tasks"
# - [ ] T1: <title> — <one-line brief>
# - [ ] T2: <title> — <brief> (after: T1)
# The brief may itself contain parentheses; only a trailing "(after: ...)"
# group is special, so it's stripped separately before the base line is matched.
TASK_AFTER_SUFFIX_RE = re.compile(r" \(after: (T\d+(?:, T\d+)*)\)$")
TASK_LINE_RE = re.compile(r"^- \[[ xX]\] (T\d+): [^—]+ — .+$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


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
        violations.append(
            "unclosed YAML frontmatter: file opens with '---' but the block never closes"
        )
        return violations
    if parsed is None:
        violations.append(
            "missing YAML frontmatter: file must open with a '---' delimited block"
        )
        return violations
    frontmatter, _body = parsed

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

    mode = frontmatter.get(EXECUTION_MODE_KEY)
    if mode and mode not in EXECUTION_MODES:
        violations.append(
            f"invalid {EXECUTION_MODE_KEY}: {mode!r} (expected one of {', '.join(EXECUTION_MODES)})"
        )

    tracker = frontmatter.get(TRACKER_KEY)
    container = frontmatter.get(CONTAINER_KEY)
    if tracker and tracker not in TRACKERS:
        violations.append(
            f"invalid {TRACKER_KEY}: {tracker!r} (expected one of {', '.join(TRACKERS)})"
        )
    if bool(tracker) != bool(container):
        violations.append(
            f"{TRACKER_KEY} and {CONTAINER_KEY} must be set together; got "
            f"{TRACKER_KEY}={tracker!r}, {CONTAINER_KEY}={container!r}"
        )

    if status in PUBLISHED_STATUSES:
        if frontmatter.get(APPROVAL_KEY) != "true":
            violations.append(
                f"missing approval for status={status}: set '{APPROVAL_KEY}: true' in the frontmatter"
            )
        if not container:
            violations.append(
                f"missing {CONTAINER_KEY} for status={status}: a published spec records its tracker container"
            )

    tasks_section = extract_section(_body, TASKS_HEADING)
    if tasks_section is not None:
        violations.extend(validate_tasks_section(tasks_section))

    return violations


def validate_tasks_section(section: str) -> list[str]:
    violations: list[str] = []
    section = HTML_COMMENT_RE.sub("", section)
    lines = [line for line in section.splitlines() if line.strip() and line.strip() != "---"]

    task_ids: set[str] = set()
    parsed: list[tuple[str, str, str | None]] = []
    for line in lines:
        afters: str | None = None
        after_match = TASK_AFTER_SUFFIX_RE.search(line)
        base_line = line
        if after_match is not None:
            afters = after_match.group(1)
            base_line = line[: after_match.start()]
        match = TASK_LINE_RE.match(base_line)
        if match is None:
            violations.append(f"malformed task line: {line!r}")
            continue
        task_id = match.group(1)
        if task_id in task_ids:
            violations.append(f"duplicate task id {task_id!r} in task line: {line!r}")
        task_ids.add(task_id)
        parsed.append((task_id, line, afters))

    for task_id, line, afters in parsed:
        if not afters:
            continue
        for ref in afters.split(", "):
            if ref == task_id:
                violations.append(
                    f"self-referential 'after' reference to {ref!r} in task line: {line!r}"
                )
            elif ref not in task_ids:
                violations.append(
                    f"dangling 'after' reference to unknown task {ref!r} in task line: {line!r}"
                )

    return violations


SECTION_END_RE = re.compile(r"^(?:## |---\s*$)", re.MULTILINE)


def extract_section(text: str, heading: str) -> str | None:
    heading_re = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    heading_match = heading_re.search(text)
    if heading_match is None:
        return None
    start = heading_match.end()
    end_match = SECTION_END_RE.search(text, start)
    return text[start : end_match.start()] if end_match else text[start:]


def validate_issue(text: str) -> list[str]:
    violations: list[str] = []
    for heading in ISSUE_SECTIONS:
        if heading not in text:
            violations.append(f"missing section heading: {heading}")

    acceptance_criteria = extract_section(text, "## Acceptance criteria")
    if acceptance_criteria is not None and not CHECKLIST_ITEM_RE.search(
        acceptance_criteria
    ):
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

    spec_parser = subparsers.add_parser(
        "spec", help="Validate a spec's frontmatter and marker"
    )
    spec_parser.add_argument("path")
    spec_parser.add_argument("--previous-status")

    issue_parser = subparsers.add_parser(
        "issue", help="Validate an issue body's required sections"
    )
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
