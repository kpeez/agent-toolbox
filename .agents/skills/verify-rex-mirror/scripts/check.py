#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Model-check the rex-agents mirror block lifecycle (RexMirror.tla) with TLC.

Exits 0 only when every run in RUNS gives its expected result: each rule holds
on the current code, each known finding still breaks, and each past bug and
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
SPEC = SKILL / "RexMirror.tla"

BASE = {
    "Mirrors": '{"m1"}',
    "Codes": "{0, 1}",
    "Kinds": '{"plain", "exec"}',
    "KillFrom": '"start"',
    "ReplyCanTimeOut": "FALSE",
    "EndOn": "TRUE",
    "WaiterOn": "TRUE",
    "Watched": '"m1"',
    "Variant": '"fixed"',
}
TWO = {"Mirrors": '{"m1", "m2"}', "Kinds": '{"plain"}', "WaiterOn": "FALSE"}

ALL_RULES = [
    "ExitLineWritten",
    "ReportsCommandStatus",
    "NoLostRow",
    "SettledBlockCloses",
    "EndPassClosesSettledRows",
    "NeverCloseWorking",
    "WaiterStartedOpenSeesOutcome",
    "LateWaiterSeesOutcome",
]
WAITER_RULES = {"WaiterStartedOpenSeesOutcome", "LateWaiterSeesOutcome"}


@dataclass
class Run:
    name: str
    kind: str  # "holds", "finding", "past bug", or "mutant"
    rules: list[str]
    overrides: dict[str, str] = field(default_factory=dict)

    @property
    def breaks(self) -> bool:
        return self.kind != "holds"


def holds(name: str, overrides: dict[str, str], without: set[str]) -> Run:
    return Run(name, "holds", [r for r in ALL_RULES if r not in without], overrides)


RUNS = [
    # The current code.
    holds(
        "current code, one mirror, kill after the handlers",
        {"KillFrom": '"reading"'},
        {"LateWaiterSeesOutcome"},
    ),
    holds(
        "current code, one mirror, kill at any step",
        {},
        {"ExitLineWritten", "LateWaiterSeesOutcome"},
    ),
    holds(
        "current code, two mirrors",
        TWO,
        {"ExitLineWritten", "NoLostRow"} | WAITER_RULES,
    ),
    # Findings in the current code. Each is replayed against the real code (SKILL.md).
    Run(
        "finding: a kill before the handlers leaves the block working",
        "finding",
        ["ExitLineWritten"],
    ),
    Run(
        "finding: session_end loses a row that remember appends",
        "finding",
        ["NoLostRow"],
        TWO,
    ),
    Run(
        "finding: a waiter that starts after the close gets 'not found'",
        "finding",
        ["LateWaiterSeesOutcome"],
    ),
    Run(
        "finding: a late `rex run` reply leaves a settled block open",
        "finding",
        ["SettledBlockCloses"],
        {"ReplyCanTimeOut": "TRUE"},
    ),
    Run(
        "finding: a late `rex run` reply crashes the viewer before a waiter sees the status",
        "finding",
        ["WaiterStartedOpenSeesOutcome"],
        {"ReplyCanTimeOut": "TRUE"},
    ),
    # Past bugs: each variant is the code before its fix.
    Run(
        "2a8e0e6: the EXIT-trap wrapper loses the marker",
        "past bug",
        ["ReportsCommandStatus"],
        {"Variant": '"trapWrapper"', "Kinds": '{"exec"}'},
    ),
    Run(
        "d53f272: a mirror with no signal handlers leaves the block working",
        "past bug",
        ["ExitLineWritten"],
        {"Variant": '"noSignalHandlers"', "KillFrom": '"reading"'},
    ),
    Run(
        "d53f272: session_end aborts on one unreadable row",
        "past bug",
        ["EndPassClosesSettledRows"],
        TWO | {"Variant": '"endPassAborts"'},
    ),
    Run(
        "9338e63: the viewer never closes its block",
        "past bug",
        ["SettledBlockCloses"],
        {"Variant": '"noViewerClose"'},
    ),
    Run(
        "9338e63: session_end keeps error blocks",
        "past bug",
        ["EndPassClosesSettledRows"],
        {"Variant": '"endPassKeepsError"'},
    ),
    # Mutants for the rules that no past bug broke.
    Run(
        "mutant: the viewer closes before it reports the status",
        "mutant",
        ["NeverCloseWorking"],
        {"Variant": '"closeBeforeStatus"'},
    ),
    Run(
        "mutant: the viewer closes before it reports the status",
        "mutant",
        ["WaiterStartedOpenSeesOutcome"],
        {"Variant": '"closeBeforeStatus"'},
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
    (folder / "run.cfg").write_text(config(run))
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
    # The last match: TLC's Progress lines print running counts first.
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
    work = ROOT / ".agents" / "scratch" / f"verify-rex-mirror-{uuid.uuid4().hex[:8]}"
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
