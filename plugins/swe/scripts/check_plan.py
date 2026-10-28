#!/usr/bin/env python3
"""Check a multi-phase plan against the plan-multi-phase skeleton.

Prints one summary line per PR section, then one line per problem on stderr
as <file>:<line>: <problem>. Exits 0 when the plan has no problems, 1 when it
has problems, and 2 on a usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

RULE = (
    "Tests alone are not sufficient verification. A PR is verified only when"
    " its unit, live, and perf boxes are all checked."
)
LANES = re.compile(r"Ten lanes on `[^`<>]+` at the PR head")
SUB_BLOCKS = [
    "Depends on.",
    "Files.",
    "Build.",
    "You see.",
    "Verify, unit.",
    "Verify, live.",
    "Verify, perf.",
    "Review gate.",
    "Merge.",
]
PROGRAM_H3 = ["Arm the program", "Spawn owners", "PR mechanics", "Verdict and merge", "Boot recipe"]
PROGRAM_MARKERS = ["Re-read", "/loop 1h", "status message"]
HOW_TO_READ_MARKERS = [
    "One box is one unit of work",
    "names the evidence",
    "Check a box only when its evidence exists",
    "playbooks/",
    RULE,
]
PERF_ITEMS = ["Metric.", "Probe.", "Baseline.", "Rule."]
BOX = re.compile(r"^\s*- \[[ x]\] (.*)$")
OPEN_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CLOSE_FENCE = re.compile(r"^ {0,3}(`+|~+)[ \t]*$")
SUB_HEAD = re.compile(r"^\*\*([^*]+)\*\*(.*)$")
LANE = re.compile(r"^Lane (\d+)\. ")


@dataclass
class Line:
    n: int
    text: str
    code: bool


@dataclass
class Section:
    title: str
    n: int
    body: list[Line] = field(default_factory=list)


@dataclass
class Block:
    name: str
    n: int
    rest: str
    lines: list[Line] = field(default_factory=list)


def opening_fence(text: str) -> tuple[str, int] | None:
    match = OPEN_FENCE.match(text)
    if not match or (match.group(1)[0] == "`" and "`" in match.group(2)):
        return None
    return match.group(1)[0], len(match.group(1))


def closing_fence(text: str, opening: tuple[str, int]) -> bool:
    match = CLOSE_FENCE.match(text)
    return bool(match and match.group(1)[0] == opening[0] and len(match.group(1)) >= opening[1])


def boxes(lines: list[Line]) -> list[tuple[int, str]]:
    found = []
    for line in lines:
        if line.code:
            continue
        match = BOX.match(line.text)
        if match:
            found.append((line.n, match.group(1)))
    return found


def check(path: str) -> tuple[list[str], list[str]]:
    with open(path, encoding="utf-8") as handle:
        raw = handle.read().splitlines()
    problems: list[str] = []

    def fail(n: int, message: str) -> None:
        problems.append(f"{path}:{n}: {message}")

    start = 0
    if raw and raw[0] == "---":
        try:
            start = raw.index("---", 1) + 1
        except ValueError:
            start = 0

    lines: list[Line] = []
    fence = None
    for i in range(start, len(raw)):
        text = raw[i]
        n = i + 1
        code = fence is not None
        if fence is not None and closing_fence(text, fence):
            code = False
            fence = None
        elif fence is None:
            fence = opening_fence(text)
            code = fence is not None
        lines.append(Line(n, text, code))
        if code:
            continue
        prose = re.sub(r"(?<!`)(`+)(?!`)(.*?)(?<!`)\1(?!`)", "`", text)
        prose = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", prose)
        prose = re.sub(r"\]\([^)]*\)", "]", prose)
        if re.search("[\u2013\u2014]", prose):
            fail(n, "long dash")
        if re.search("[\u2018\u2019\u201c\u201d]", prose):
            fail(n, "curly quote")
        if re.search(r": \S", prose):
            fail(n, "mid-sentence colon")

    sections: list[Section] = []
    for line in lines:
        if not line.code and line.text.startswith("## "):
            sections.append(Section(line.text[3:].strip(), line.n))
        elif sections:
            sections[-1].body.append(line)

    def find(title: str) -> Section | None:
        return next((s for s in sections if s.title == title), None)

    def body_text(section: Section) -> str:
        return "\n".join(line.text for line in section.body)

    h1 = next((i for i, line in enumerate(lines) if not line.code and line.text.startswith("# ")), -1)
    if h1 == -1:
        fail(1, "no H1 title")
    how_to_read = find("How to read this")
    if how_to_read is None:
        fail(1, 'no "## How to read this" section')
    if h1 != -1 and how_to_read is not None:
        intro = [
            line for line in lines[h1 + 1 :] if line.n < how_to_read.n and line.text.strip() != ""
        ]
        if len(intro) >= 10:
            fail(lines[h1].n, f"intro is {len(intro)} lines, under ten required")
        for marker in HOW_TO_READ_MARKERS:
            if marker not in body_text(how_to_read):
                fail(how_to_read.n, f'How to read this lacks "{marker}"')

    program = find("Program checklist")
    if program is None:
        fail(1, 'no "## Program checklist" section')
    else:
        h3s = [
            line.text[4:].strip()
            for line in program.body
            if not line.code and line.text.startswith("### ")
        ]
        cursor = 0
        for name in PROGRAM_H3:
            at = next((i for i, t in enumerate(h3s) if i >= cursor and t.startswith(name)), -1)
            if at == -1:
                fail(program.n, f'Program checklist lacks "### {name}" in order')
            else:
                cursor = at + 1
        for marker in PROGRAM_MARKERS:
            if marker not in body_text(program):
                fail(program.n, f'Program checklist lacks "{marker}"')

    close = find("Close the program")
    if close is None:
        fail(1, 'no "## Close the program" section')
    program_index = sections.index(program) if program is not None else -1
    close_index = sections.index(close) if close is not None else -1
    pr_sections = (
        [] if program_index == -1 or close_index == -1 else sections[program_index + 1 : close_index]
    )
    if not pr_sections:
        fail(1, "no PR sections between Program checklist and Close the program")

    report: list[str] = []
    for pr in pr_sections:
        heads: list[Block] = []
        for line in pr.body:
            if line.code:
                continue
            match = SUB_HEAD.match(line.text)
            if match and match.group(1) in SUB_BLOCKS:
                heads.append(Block(match.group(1), line.n, match.group(2).strip()))
            elif heads:
                heads[-1].lines.append(line)
        names = [h.name for h in heads]
        if names != SUB_BLOCKS:
            fail(pr.n, f"{pr.title}: sub-blocks are [{', '.join(names)}], expected [{', '.join(SUB_BLOCKS)}]")

        def block(name: str) -> Block | None:
            return next((h for h in heads if h.name == name), None)

        counts = {h.name: len(boxes(h.lines)) for h in heads}

        depends = block("Depends on.")
        if depends is not None and depends.rest == "":
            fail(depends.n, f"{pr.title}: Depends on names nothing")
        for name in ["Files.", "Build.", "You see.", "Verify, unit.", "Merge."]:
            b = block(name)
            if b is not None and not boxes(b.lines):
                fail(b.n, f"{pr.title}: {name} has no box")
        for name in ["Verify, unit.", "Verify, live.", "Verify, perf."]:
            b = block(name)
            if b is not None and not b.rest.startswith(RULE):
                fail(b.n, f"{pr.title}: {name} does not open with the rule")

        live = block("Verify, live.")
        if live is not None:
            if not LANES.search(live.rest):
                fail(
                    live.n,
                    f'{pr.title}: Verify, live lacks "Ten lanes on `<model>` at the PR head"'
                    " with the model filled in",
                )
            lanes = [(n, text, LANE.match(text)) for n, text in boxes(live.lines)]
            numbers = sorted(int(m.group(1)) for _, _, m in lanes if m)
            if numbers != list(range(1, 11)):
                fail(live.n, f"{pr.title}: lanes are [{','.join(map(str, numbers))}], expected 1 to 10")
            for n, text, m in lanes:
                if not m:
                    fail(n, f"{pr.title}: live box is not a lane")
                elif not re.search(r"Save `[^`]+`", text):
                    fail(n, f"{pr.title}: lane {m.group(1)} names no screenshot")
                elif "Pass when" not in text:
                    fail(n, f"{pr.title}: lane {m.group(1)} has no pass predicate")

        perf = block("Verify, perf.")
        if perf is not None:
            items = [text.split(" ")[0] for _, text in boxes(perf.lines)]
            if items != PERF_ITEMS:
                fail(perf.n, f"{pr.title}: perf boxes are [{', '.join(items)}], expected [{', '.join(PERF_ITEMS)}]")

        gate = block("Review gate.")
        if gate is not None:
            gate_boxes = boxes(gate.lines)
            if gate.rest.startswith("None."):
                if gate_boxes:
                    fail(gate.n, f"{pr.title}: Review gate says None but has boxes")
            else:
                text = "\n".join(line.text for line in gate.lines)
                if not gate_boxes:
                    fail(gate.n, f"{pr.title}: Review gate has no box")
                for word in ["screenshot", "video", "operator"]:
                    if word not in text:
                        fail(gate.n, f'{pr.title}: Review gate lacks "{word}"')

        total = len(boxes(pr.body))
        cells = []
        for name in SUB_BLOCKS[1:]:
            key = re.sub(r"[ ,.]+", "-", name).rstrip("-").lower()
            cells.append(f"{key}={counts.get(name, 0)}")
        report.append(f"{pr.title}  boxes={total}  {' '.join(cells)}")

    if close is not None:
        tail = sections[close_index + 1 :]
        for section in tail:
            if not section.title.startswith("Appendix"):
                fail(section.n, f'"## {section.title}" after Close the program is not an appendix')
        if not any("Prototype evidence" in s.title for s in tail):
            fail(close.n, 'no "## Appendix ... Prototype evidence" section')

    report.append(f"{len(pr_sections)} PR sections, {len(problems)} problems")
    return report, problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check a multi-phase plan against the plan-multi-phase skeleton: required sections"
            " and sub-blocks, the verification rule, ten live lanes, perf items, the review gate,"
            " and prose rules (no long dash, curly quote, or mid-sentence colon outside code)."
        ),
    )
    parser.add_argument("plan", help="path to the plan markdown file")
    args = parser.parse_args()
    try:
        report, problems = check(args.plan)
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for line in report:
        print(line)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
