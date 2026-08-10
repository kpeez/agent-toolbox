#!/usr/bin/env python3
"""Validate the retained artifacts of one completed deep-research run."""

from __future__ import annotations

import re
import sys
from pathlib import Path

EVIDENCE_ID = re.compile(r"^###\s+(E[0-9][A-Za-z0-9_-]*)\b", re.MULTILINE)
CITATION = re.compile(r"\[(E[0-9][A-Za-z0-9_-]*)\]")
STOP_REASON = re.compile(
    r"^## Stop reason\s*$\n+([^\n]+)", re.MULTILINE | re.IGNORECASE
)
VALID_STOPS = ("coverage", "budget", "diminishing returns")
BRIEF_SECTIONS = (
    "Research question",
    "Decision or deliverable",
    "Scope and exclusions",
    "Freshness and source standard",
    "Lanes and boundaries",
    "Budgets",
    "Coverage requirements",
    "Requested outputs",
    "Constraints and assumptions",
)
LANE_SECTIONS = (
    "Question and boundary",
    "Answer",
    "Source records",
    "Claim-to-source map",
    "Contradictions and uncertainty",
    "Unavailable sources and failed searches",
    "Untrusted content",
    "Lane stop",
)
REPORT_SECTIONS = (
    "Answer",
    "Findings",
    "Contradictions and uncertainty",
    "Stop reason",
    "Sources",
)


def read_required(root: Path, name: str) -> str:
    path = root / name
    if not path.is_file():
        raise ValueError(f"missing required artifact: {name}")
    text = path.read_text()
    if not text.strip():
        raise ValueError(f"required artifact is empty: {name}")
    return text


def section(text: str, heading: str, source: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"{source} is missing nonempty section '## {heading}'")
    following = text[match.end() :]
    next_heading = re.search(r"^## ", following, re.MULTILINE)
    body = following[: next_heading.start() if next_heading else None].strip()
    if not body:
        raise ValueError(f"{source} is missing nonempty section '## {heading}'")
    return body


def required_field(text: str, name: str, source: str) -> str:
    match = re.search(rf"^- {re.escape(name)}:\s*(\S.*?)\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"{source} is missing nonempty field '- {name}: ...'")
    return match.group(1)


def validate_lane(text: str, source: str) -> None:
    if not re.search(r"^# Lane:\s*\S", text, re.MULTILINE):
        raise ValueError(f"{source} is missing '# Lane: ...'")
    lane_sections = {name: section(text, name, source) for name in LANE_SECTIONS}
    boundary = lane_sections["Question and boundary"]
    for name in (
        "Question",
        "Boundary",
        "In scope",
        "Out of scope",
        "Budget",
        "Budget used",
    ):
        required_field(boundary, name, source)
    if required_field(boundary, "Boundary", source) not in {"web-only", "repository"}:
        raise ValueError(f"{source} has invalid Boundary")

    records = re.split(
        r"(?=^### S[0-9]+\b)", lane_sections["Source records"], flags=re.MULTILINE
    )
    records = [record for record in records if re.match(r"^### S[0-9]+\b", record)]
    if not records:
        raise ValueError(f"{source} has no source records")
    for record in records:
        for name in (
            "Location",
            "Publisher/author",
            "Published/version",
            "Retrieved",
            "Type",
            "Supports",
            "Passage summary",
            "Caveats",
            "Status",
        ):
            required_field(record, name, source)
    if not re.search(
        r"^- C[0-9]+:\s*\S.*→\s*S[0-9]+\b",
        lane_sections["Claim-to-source map"],
        re.MULTILINE,
    ):
        raise ValueError(f"{source} has no claim-to-source records")
    contradictions = lane_sections["Contradictions and uncertainty"]
    contradiction_status = required_field(contradictions, "Status", source)
    if contradiction_status not in {"none", "present"}:
        raise ValueError(f"{source} has invalid contradiction Status")
    contradiction_record = required_field(contradictions, "Record", source)
    if contradiction_status == "present" and contradiction_record == "none":
        raise ValueError(f"{source} contradiction Record must describe the conflict")
    failed_searches = lane_sections["Unavailable sources and failed searches"]
    failed_attempts = required_field(failed_searches, "Attempts", source)
    untrusted = lane_sections["Untrusted content"]
    untrusted_status = required_field(untrusted, "Status", source)
    if untrusted_status not in {"none", "present"}:
        raise ValueError(f"{source} has invalid Untrusted content Status")
    untrusted_record = required_field(untrusted, "Record", source)
    if untrusted_status == "present" and "ignored" not in untrusted_record.lower():
        raise ValueError(f"{source} untrusted-content Record must say it was ignored")
    lane_stop = lane_sections["Lane stop"]
    reason = required_field(lane_stop, "Reason", source)
    if reason not in {"answered", "budget", "diminishing returns"}:
        raise ValueError(f"{source} has invalid Lane stop Reason")
    required_field(lane_stop, "Remaining gap", source)
    if reason == "diminishing returns" and failed_attempts == "none":
        raise ValueError(
            f"{source} diminishing-returns stop requires failed-search records"
        )


def validate_evidence(text: str) -> tuple[set[str], str]:
    source_records = section(text, "Source records", "evidence.md")
    claim_map = section(text, "Claim map", "evidence.md")
    contradictions = section(
        text, "Contradictions and unsupported claims", "evidence.md"
    )
    contradiction_status = required_field(contradictions, "Status", "evidence.md")
    if contradiction_status not in {"none", "present"}:
        raise ValueError("evidence.md has invalid contradiction Status")
    contradiction_record = required_field(contradictions, "Record", "evidence.md")
    if contradiction_status == "present" and contradiction_record == "none":
        raise ValueError("evidence.md contradiction Record must describe the conflict")
    reconciliation = section(text, "Reconciliation", "evidence.md")
    round_value = required_field(reconciliation, "Round", "evidence.md")
    if round_value not in {"none", "one"}:
        raise ValueError("evidence.md Reconciliation Round must be none or one")
    trigger = required_field(reconciliation, "Trigger", "evidence.md")
    result = required_field(reconciliation, "Result", "evidence.md")
    if contradiction_status == "present" and round_value != "one":
        raise ValueError(
            "evidence.md present contradictions require one reconciliation round"
        )
    if round_value == "none" and (trigger != "none" or result == "none"):
        raise ValueError(
            "evidence.md no-round reconciliation must record Trigger: none and a result"
        )

    records = re.split(
        r"(?=^### E[0-9][A-Za-z0-9_-]*\b)", source_records, flags=re.MULTILINE
    )
    records = [record for record in records if EVIDENCE_ID.match(record)]
    if not records:
        raise ValueError("evidence.md contains no evidence records such as '### E1'")
    evidence_ids = set()
    identities = set()
    for record in records:
        evidence_id = EVIDENCE_ID.match(record)
        assert evidence_id
        evidence_ids.add(evidence_id.group(1))
        fields = {
            name: required_field(record, name, "evidence.md")
            for name in (
                "Location",
                "Version",
                "Retrieved",
                "Lanes",
                "Claims",
                "Status",
                "Caveats",
            )
        }
        identity = (fields["Location"], fields["Version"])
        if identity in identities:
            raise ValueError(
                "evidence.md repeats a source identity instead of deduplicating it"
            )
        identities.add(identity)
    if not re.search(r"^- C[0-9]+:\s*\S.*→\s*E[0-9]", claim_map, re.MULTILINE):
        raise ValueError("evidence.md has no normalized claim records")
    return evidence_ids, contradiction_status


def validate(root: Path) -> None:
    brief = read_required(root, "brief.md")
    evidence = read_required(root, "evidence.md")
    report = read_required(root, "report.md")

    for name in BRIEF_SECTIONS:
        section(brief, name, "brief.md")
    for name in REPORT_SECTIONS:
        section(report, name, "report.md")
    report_contradictions = section(
        report, "Contradictions and uncertainty", "report.md"
    )
    report_status = required_field(report_contradictions, "Status", "report.md")
    if report_status not in {"none", "reconciled", "unresolved"}:
        raise ValueError("report.md has invalid contradiction Status")
    required_field(report_contradictions, "Record", "report.md")

    lanes = root / "lanes"
    if not lanes.is_dir():
        raise ValueError("missing required artifact directory: lanes")
    lane_files = sorted(lanes.glob("*.md"))
    if not lane_files:
        raise ValueError("no retained lane packets found in lanes")
    for lane in lane_files:
        validate_lane(lane.read_text(), f"lanes/{lane.name}")

    match = STOP_REASON.search(report)
    if not match or not any(
        re.match(rf"^{re.escape(stop)}\b", match.group(1).strip(), re.IGNORECASE)
        for stop in VALID_STOPS
    ):
        raise ValueError(
            "report Stop reason must begin with coverage, budget, or diminishing returns"
        )

    evidence_ids, contradiction_status = validate_evidence(evidence)
    if contradiction_status == "present" and report_status == "none":
        raise ValueError("report.md omits normalized contradictions")
    final_text = report
    proposal = root / "proposal.md"
    if proposal.is_file():
        final_text += "\n" + proposal.read_text()
    citations = set(CITATION.findall(final_text))
    if not citations:
        raise ValueError("final output contains no evidence citations such as [E1]")
    unknown = sorted(citations - evidence_ids)
    if unknown:
        raise ValueError(
            f"final citations missing from evidence.md: {', '.join(unknown)}"
        )


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} RUN_DIR", file=sys.stderr)
        return 2
    try:
        validate(Path(sys.argv[1]).resolve())
    except (OSError, ValueError) as error:
        print(f"invalid deep-research run: {error}", file=sys.stderr)
        return 1
    print("deep-research artifacts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
