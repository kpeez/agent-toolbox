#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Model-check the swe pull-request lifecycle (PrLifecycle.tla) with TLC.

Exits 0 only when every run in RUNS gives its expected result: each rule holds
on the current protocol, each known finding still breaks, and each past bug and
mutant breaks the rule it targets. For a rule that breaks, prints TLC's
shortest path as a list of actions.

TLC and Java: TLA2TOOLS and JAVA from the environment, or the statechart
skill's pins through .github/scripts/statechart_tlc.py.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ROOT = SKILL.parent.parent.parent
SPEC = SKILL / "PrLifecycle.tla"
CHART = SKILL / "chart.cfg"

BASE = {
    "Prs": "1",
    "Requests": '{"hold", "publish", "finalize", "implement"}',
    "MaxPushes": "2",
    "StackMergeOn": "FALSE",
    "Variant": '"current"',
}
STACK_OF_THREE = {"Prs": "3"}
STACK_OF_TWO = {"Prs": "2", "MaxPushes": "1"}

ALL_RULES = [
    "MergedPatchVerified",
    "DoneOnlyAfterMerge",
    "IssueNeverBackward",
    "DraftUntilLandOrFinalize",
    "ActsWithAuthority",
    "MergeAtFrontier",
]


@dataclass
class Run:
    name: str
    kind: str
    rules: list[str]
    overrides: dict[str, str] = field(default_factory=dict)
    config_file: Path | None = None

    @property
    def breaks(self) -> bool:
        return self.kind != "holds"


RUNS = [
    Run("current protocol, one PR, every request, two pushes", "holds", ALL_RULES),
    Run(
        "current protocol, a stack of three, pinned merges from the bottom, two pushes",
        "holds",
        ALL_RULES,
        STACK_OF_THREE,
    ),
    Run(
        "current protocol, a stack of three, gh stack merge, no push after publish",
        "holds",
        ALL_RULES,
        STACK_OF_THREE | {"StackMergeOn": "TRUE", "MaxPushes": "0"},
    ),
    Run("the chart config (chart.cfg)", "holds", ALL_RULES, config_file=CHART),
    Run(
        "finding: gh stack merge lands a head pushed after the recheck",
        "finding",
        ["MergedPatchVerified"],
        STACK_OF_TWO | {"StackMergeOn": "TRUE"},
    ),
    Run(
        "finding: ship-stack step 3 and autopilot-full keep a verdict across a tests-or-docs push",
        "finding",
        ["MergedPatchVerified"],
        {"Variant": '"noiseCarry"'},
    ),
    Run(
        "c491b05: the proactive ship-pr opens a draft PR with no request",
        "past bug",
        ["ActsWithAuthority"],
        {"Variant": '"proactivePublish"'},
    ),
    Run(
        "c491b05: Finalize moves the issue to done when it marks the PR ready",
        "past bug",
        ["DoneOnlyAfterMerge"],
        {"Variant": '"finalizeMovesDone"'},
    ),
    Run(
        "c57bc85: a request marks a draft ready outside Land and Finalize",
        "past bug",
        ["DraftUntilLandOrFinalize"],
        {"Variant": '"readyOnRequest"'},
    ),
    Run(
        "mutant: Land merges without --match-head-commit",
        "mutant",
        ["MergedPatchVerified"],
        {"Variant": '"unpinnedMerge"'},
    ),
    Run(
        "mutant: a verified PR above the frontier merges",
        "mutant",
        ["MergeAtFrontier"],
        STACK_OF_TWO | {"Variant": '"anyVerifiedMerges"'},
    ),
    Run(
        "mutant: Finalize moves the issue to review after the merge",
        "mutant",
        ["IssueNeverBackward"],
        {"Variant": '"reviewAfterMerge"'},
    ),
]


def tlc() -> tuple[str, str]:
    jar, java = os.environ.get("TLA2TOOLS"), os.environ.get("JAVA")
    if jar:
        return jar, java or "java"
    out = subprocess.run(
        ["uv", "run", str(ROOT / ".github" / "scripts" / "statechart_tlc.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    found = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return found["TLA2TOOLS"], found["JAVA"]


def config(run: Run) -> str:
    consts = BASE | run.overrides
    lines = ["CONSTANTS", *(f"  {k} = {v}" for k, v in consts.items())]
    lines += [
        "INIT Init",
        "NEXT Next",
        "CHECK_DEADLOCK FALSE",
        "INVARIANTS",
        *(f"  {r}" for r in run.rules),
    ]
    return "\n".join(lines) + "\n"


def check(run: Run, index: int, work: Path, jar: str, java: str) -> tuple[bool, str]:
    folder = work / str(index)
    folder.mkdir()
    (folder / "run.cfg").write_text(
        run.config_file.read_text() if run.config_file else config(run)
    )
    shutil.copy(SPEC, folder / SPEC.name)
    r = subprocess.run(
        [
            java,
            "-XX:+UseParallelGC",
            # TLC writes its standard modules to the temp folder; a shared one races across runs.
            f"-Djava.io.tmpdir={folder}",
            "-cp",
            jar,
            "tlc2.TLC",
            "-workers",
            "1",
            "-deadlock",
            "-metadir",
            str(folder / "states"),
            "-config",
            "run.cfg",
            SPEC.name,
        ],
        check=False,
        cwd=folder,
        capture_output=True,
        text=True,
    )
    out = r.stdout + r.stderr
    broken = re.findall(r"Invariant (\w+) is violated", out)
    states = re.findall(r"([\d,]+) distinct states found", out)
    count = f"{int(states[-1].replace(',', '')):,}" if states else "?"
    if r.returncode not in (0, 12) or (r.returncode == 12) != bool(broken):
        return False, f"TLC failed (exit {r.returncode}):\n{out[-2000:]}"
    path = " -> ".join(re.findall(r"^State \d+: <(\w+)", out, re.MULTILINE))
    if run.breaks:
        ok = broken == run.rules
        detail = (
            f"{run.rules[0]} breaks, path: {path}"
            if broken
            else f"{run.rules[0]} holds"
        )
    else:
        ok = not broken
        detail = (
            f"{len(run.rules)} rules hold, {count} states"
            if ok
            else f"{broken[0]} breaks, path: {path}"
        )
    return ok, detail


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the TLC configs and output folder"
    )
    args = parser.parse_args()
    jar, java = tlc()
    work = ROOT / ".agents" / "scratch" / f"verify-pr-lifecycle-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True)
    try:
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
            results = list(
                pool.map(
                    lambda ir: check(ir[1], ir[0], work, jar, java), enumerate(RUNS)
                )
            )
    finally:
        if args.keep:
            print(f"kept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)
    failed = 0
    for run, (ok, detail) in zip(RUNS, results):
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} [{run.kind}] {run.name}: {detail}")
    if failed:
        print(
            f"{failed} run(s) did not give the expected result. Read SKILL.md, 'When the check fails'."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
